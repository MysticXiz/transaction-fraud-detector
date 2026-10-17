from __future__ import annotations

from dataclasses import dataclass
from math import log
from time import perf_counter
from typing import Literal, Protocol, cast

import numpy as np
import pyopencl as cl
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest


class OpenCLRuntimeUnavailableError(RuntimeError):
    """Raised when no usable OpenCL platform or device is available."""


class OpenCLExecutionError(RuntimeError):
    """Raised when an OpenCL kernel cannot be built or executed."""


@dataclass(frozen=True, slots=True)
class OpenCLExecutionResult:
    scores: NDArray[np.float32]
    suspicious: NDArray[np.bool_]
    chunk_ids: NDArray[np.int32]
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class _ForestArrays:
    children_left: NDArray[np.int32]
    children_right: NDArray[np.int32]
    features: NDArray[np.int32]
    thresholds: NDArray[np.float32]
    leaf_path_lengths: NDArray[np.float32]
    feature_indices: NDArray[np.int32]
    max_nodes: int
    features_per_tree: int
    denominator: np.float32


@dataclass(frozen=True, slots=True)
class _ForestDeviceBuffers:
    children_left: cl.Buffer
    children_right: cl.Buffer
    features: cl.Buffer
    thresholds: cl.Buffer
    leaf_path_lengths: cl.Buffer
    feature_indices: cl.Buffer


class _TreeStructure(Protocol):
    @property
    def node_count(self) -> int: ...

    @property
    def children_left(self) -> NDArray[np.int64]: ...

    @property
    def children_right(self) -> NDArray[np.int64]: ...

    @property
    def feature(self) -> NDArray[np.int64]: ...

    @property
    def threshold(self) -> NDArray[np.float64]: ...

    @property
    def n_node_samples(self) -> NDArray[np.int64]: ...


_ISOLATION_SCORE_KERNEL = r"""
__kernel void score_isolation_forest(
    __global const float *samples,
    const uint n_samples,
    const uint n_features,
    const uint n_trees,
    const uint max_nodes,
    const uint features_per_tree,
    __global const int *children_left,
    __global const int *children_right,
    __global const int *tree_features,
    __global const float *thresholds,
    __global const float *leaf_path_lengths,
    __global const int *feature_indices,
    const float denominator,
    __global float *scores)
{
    const uint sample_id = get_global_id(0);
    if (sample_id >= n_samples) {
        return;
    }

    float path_length_sum = 0.0f;
    for (uint tree_id = 0; tree_id < n_trees; ++tree_id) {
        const uint tree_offset = tree_id * max_nodes;
        int node_id = 0;
        int depth = 0;
        while (children_left[tree_offset + node_id] >= 0) {
            const int local_feature = tree_features[tree_offset + node_id];
            const int feature_id =
                feature_indices[tree_id * features_per_tree + local_feature];
            const float value = samples[sample_id * n_features + feature_id];
            if (value <= thresholds[tree_offset + node_id]) {
                node_id = children_left[tree_offset + node_id];
            } else {
                node_id = children_right[tree_offset + node_id];
            }
            ++depth;
        }
        path_length_sum +=
            (float)depth + leaf_path_lengths[tree_offset + node_id];
    }

    scores[sample_id] = exp2(-path_length_sum / denominator);
}
"""


class OpenCLIsolationForestExecutor:
    """Fits Isolation Forest on CPU and scores every transaction with OpenCL."""

    def __init__(
        self,
        *,
        n_estimators: int = 200,
        contamination: float | Literal["auto"] = 0.0017,
        random_state: int = 42,
    ):
        self._model = IsolationForest(
            n_estimators=n_estimators,
            max_samples="auto",
            contamination=contamination,
            random_state=random_state,
            n_jobs=1,
        )
        self._forest: _ForestArrays | None = None
        self._forest_buffers: _ForestDeviceBuffers | None = None
        self._context: cl.Context | None = None
        self._queue: cl.CommandQueue | None = None
        self._kernel: cl.Kernel | None = None
        self._device: cl.Device | None = None

    @staticmethod
    def available_device() -> tuple[str, str]:
        device = _select_device()
        return device.platform.name, device.name

    def fit(self, features: NDArray[np.number]) -> OpenCLIsolationForestExecutor:
        matrix = _validate_matrix(features, minimum_rows=2)
        self._model.fit(matrix)
        self._forest = _pack_forest(self._model)
        self._forest_buffers = None
        return self

    def score_opencl(
        self,
        features: NDArray[np.number],
        *,
        work_group_size: int | None = None,
    ) -> NDArray[np.float32]:
        forest = self._require_fitted()
        matrix = _validate_matrix(
            features, expected_features=self._model.n_features_in_
        )
        if matrix.shape[0] == 0:
            return np.empty(0, dtype=np.float32)

        context, queue, kernel, device = self._get_runtime()
        local_size = self._validate_work_group_size(work_group_size, kernel, device)
        samples = np.ascontiguousarray(matrix, dtype=np.float32)
        if not np.isfinite(samples).all():
            raise ValueError("As features excedem o intervalo suportado pelo OpenCL")
        scores = np.empty(samples.shape[0], dtype=np.float32)
        memory_flags = cl.mem_flags

        try:
            forest_buffers = self._get_forest_buffers(context, forest)
            sample_buffer = cl.Buffer(
                context,
                memory_flags.READ_ONLY | memory_flags.COPY_HOST_PTR,
                hostbuf=samples,
            )
            scores_buffer = cl.Buffer(context, memory_flags.WRITE_ONLY, scores.nbytes)

            global_size = samples.shape[0]
            if local_size is not None:
                global_size = (
                    (global_size + local_size - 1) // local_size
                ) * local_size
            kernel(
                queue,
                (global_size,),
                (local_size,) if local_size is not None else None,
                sample_buffer,
                np.uint32(samples.shape[0]),
                np.uint32(samples.shape[1]),
                np.uint32(len(self._model.estimators_)),
                np.uint32(forest.max_nodes),
                np.uint32(forest.features_per_tree),
                forest_buffers.children_left,
                forest_buffers.children_right,
                forest_buffers.features,
                forest_buffers.thresholds,
                forest_buffers.leaf_path_lengths,
                forest_buffers.feature_indices,
                forest.denominator,
                scores_buffer,
            )
            cl.enqueue_copy(queue, scores, scores_buffer).wait()
        except cl.Error as error:
            raise OpenCLExecutionError(
                f"Falha ao executar a pontuação Isolation Forest em OpenCL: {error}"
            ) from error
        return scores

    def score_sequential(self, features: NDArray[np.number]) -> NDArray[np.float64]:
        self._require_fitted()
        matrix = _validate_matrix(
            features, expected_features=self._model.n_features_in_
        )
        return -self._model.score_samples(matrix)

    def execute(
        self,
        features: NDArray[np.number],
        *,
        threshold: float = 0.5,
        chunk_size: int = 10_000,
        work_group_size: int | None = None,
    ) -> OpenCLExecutionResult:
        if not 0 <= threshold <= 1:
            raise ValueError("O limiar deve estar entre 0 e 1")
        if chunk_size < 1:
            raise ValueError("O tamanho do bloco deve ser positivo")
        matrix = _validate_matrix(features, minimum_rows=2)

        started = perf_counter()
        self.fit(matrix)
        score_chunks: list[NDArray[np.float32]] = []
        chunk_id_parts: list[NDArray[np.int32]] = []
        for chunk_id, start in enumerate(range(0, matrix.shape[0], chunk_size)):
            chunk = matrix[start : start + chunk_size]
            score_chunks.append(
                self.score_opencl(chunk, work_group_size=work_group_size)
            )
            chunk_id_parts.append(np.full(chunk.shape[0], chunk_id, dtype=np.int32))

        scores = np.concatenate(score_chunks)
        return OpenCLExecutionResult(
            scores=scores,
            suspicious=scores >= threshold,
            chunk_ids=np.concatenate(chunk_id_parts),
            elapsed_seconds=perf_counter() - started,
        )

    def _get_runtime(
        self,
    ) -> tuple[cl.Context, cl.CommandQueue, cl.Kernel, cl.Device]:
        if (
            self._context is not None
            and self._queue is not None
            and self._kernel is not None
            and self._device is not None
        ):
            return self._context, self._queue, self._kernel, self._device

        device = _select_device()
        try:
            context = cl.Context(devices=[device])
            queue = cl.CommandQueue(context, device=device)
            program = cl.Program(context, _ISOLATION_SCORE_KERNEL).build(
                devices=[device]
            )
            kernel = cl.Kernel(program, "score_isolation_forest")
        except cl.Error as error:
            raise OpenCLExecutionError(
                f"Não foi possível inicializar o dispositivo OpenCL {device.name}: "
                f"{error}"
            ) from error

        self._device = device
        self._context = context
        self._queue = queue
        self._kernel = kernel
        return context, queue, kernel, device

    def _get_forest_buffers(
        self, context: cl.Context, forest: _ForestArrays
    ) -> _ForestDeviceBuffers:
        if self._forest_buffers is None:
            self._forest_buffers = _ForestDeviceBuffers(
                children_left=_read_only_buffer(context, forest.children_left),
                children_right=_read_only_buffer(context, forest.children_right),
                features=_read_only_buffer(context, forest.features),
                thresholds=_read_only_buffer(context, forest.thresholds),
                leaf_path_lengths=_read_only_buffer(context, forest.leaf_path_lengths),
                feature_indices=_read_only_buffer(context, forest.feature_indices),
            )
        return self._forest_buffers

    @staticmethod
    def _validate_work_group_size(
        work_group_size: int | None, kernel: cl.Kernel, device: cl.Device
    ) -> int | None:
        if work_group_size is None:
            return None
        if work_group_size < 1:
            raise ValueError("O tamanho do work-group deve ser positivo")
        max_kernel_size = kernel.get_work_group_info(
            cl.kernel_work_group_info.WORK_GROUP_SIZE, device
        )
        if work_group_size > min(device.max_work_group_size, max_kernel_size):
            raise ValueError(
                "O tamanho do work-group excede o limite do dispositivo OpenCL"
            )
        return work_group_size

    def _require_fitted(self) -> _ForestArrays:
        if self._forest is None:
            raise RuntimeError("O executor precisa ser ajustado antes da pontuação")
        return self._forest


def _get_platforms() -> list[cl.Platform]:
    try:
        return cl.get_platforms()
    except cl.Error as error:
        raise OpenCLRuntimeUnavailableError(
            "Não foi possível enumerar plataformas OpenCL. Verifique se o runtime "
            f"OpenCL do fabricante está instalado: {error}"
        ) from error


def _select_device() -> cl.Device:
    platforms = _get_platforms()
    devices: list[cl.Device] = []
    errors: list[str] = []
    for platform in platforms:
        try:
            devices.extend(platform.get_devices())
        except cl.Error as error:
            errors.append(f"{platform.name}: {error}")

    if not devices:
        detail = "; ".join(errors) if errors else "nenhum dispositivo foi listado"
        raise OpenCLRuntimeUnavailableError(
            "Nenhum dispositivo OpenCL está disponível. Instale um runtime "
            f"OpenCL compatível com o hardware. Detalhes: {detail}"
        )

    devices.sort(key=lambda device: not bool(device.type & cl.device_type.GPU))
    return devices[0]


def _read_only_buffer(context: cl.Context, values: NDArray[np.generic]) -> cl.Buffer:
    return cl.Buffer(
        context,
        cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
        hostbuf=values,
    )


def _validate_matrix(
    features: NDArray[np.number],
    *,
    minimum_rows: int = 0,
    expected_features: int | None = None,
) -> NDArray[np.float64]:
    matrix = np.asarray(features, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] == 0:
        raise ValueError("As features devem formar uma matriz bidimensional")
    if matrix.shape[0] < minimum_rows:
        raise ValueError(f"São necessárias ao menos {minimum_rows} transações")
    if expected_features is not None and matrix.shape[1] != expected_features:
        raise ValueError("A quantidade de features difere daquela usada no ajuste")
    if not np.isfinite(matrix).all():
        raise ValueError("As features devem conter apenas valores finitos")
    return np.ascontiguousarray(matrix)


def _pack_forest(model: IsolationForest) -> _ForestArrays:
    trees = model.estimators_
    tree_features = model.estimators_features_
    max_nodes = max(
        cast(_TreeStructure, estimator.tree_).node_count for estimator in trees
    )
    features_per_tree = max(len(indices) for indices in tree_features)
    tree_count = len(trees)

    children_left = np.full((tree_count, max_nodes), -1, dtype=np.int32)
    children_right = np.full((tree_count, max_nodes), -1, dtype=np.int32)
    features = np.full((tree_count, max_nodes), -1, dtype=np.int32)
    thresholds = np.zeros((tree_count, max_nodes), dtype=np.float32)
    leaf_path_lengths = np.zeros((tree_count, max_nodes), dtype=np.float32)
    feature_indices = np.zeros((tree_count, features_per_tree), dtype=np.int32)

    for tree_id, (estimator, selected_features) in enumerate(
        zip(trees, tree_features, strict=True)
    ):
        tree = cast(_TreeStructure, estimator.tree_)
        node_count = tree.node_count
        children_left[tree_id, :node_count] = tree.children_left
        children_right[tree_id, :node_count] = tree.children_right
        features[tree_id, :node_count] = tree.feature
        thresholds[tree_id, :node_count] = tree.threshold
        feature_indices[tree_id, : len(selected_features)] = selected_features
        for node_id in range(node_count):
            if tree.children_left[node_id] < 0:
                leaf_path_lengths[tree_id, node_id] = _average_path_length(
                    int(tree.n_node_samples[node_id])
                )

    denominator = tree_count * _average_path_length(model.max_samples_)
    if denominator <= 0:
        raise ValueError("O modelo Isolation Forest não contém amostras suficientes")

    return _ForestArrays(
        children_left=np.ascontiguousarray(children_left),
        children_right=np.ascontiguousarray(children_right),
        features=np.ascontiguousarray(features),
        thresholds=np.ascontiguousarray(thresholds),
        leaf_path_lengths=np.ascontiguousarray(leaf_path_lengths),
        feature_indices=np.ascontiguousarray(feature_indices),
        max_nodes=max_nodes,
        features_per_tree=features_per_tree,
        denominator=np.float32(denominator),
    )


def _average_path_length(sample_count: int) -> float:
    if sample_count <= 1:
        return 0.0
    if sample_count == 2:
        return 1.0
    return 2.0 * (log(sample_count - 1) + np.euler_gamma) - (
        2.0 * (sample_count - 1) / sample_count
    )
