from __future__ import annotations

from dataclasses import dataclass
from math import log
from time import perf_counter
from typing import Literal, Protocol, cast
import logging
import os

import numpy as np
import pyopencl as cl
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


class OpenCLRuntimeUnavailableError(RuntimeError):
    """Raised when no usable OpenCL platform or device is available."""


class OpenCLExecutionError(RuntimeError):
    """Raised when an OpenCL kernel cannot be built or executed."""


OpenCLDeviceType = Literal["CPU", "GPU"]


@dataclass(frozen=True, slots=True)
class OpenCLExecutionResult:
    scores: NDArray[np.float32]
    suspicious: NDArray[np.bool_]
    chunk_ids: NDArray[np.int32]
    elapsed_seconds: float
    tempo_kernel_s: float = 0.0
    tempo_transferencia_s: float = 0.0


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


@dataclass(frozen=True, slots=True)
class OpenCLPendingResult:
    scores: NDArray[np.float32]
    chunk_id: int
    _sample_buffer: cl.Buffer
    _scores_buffer: cl.Buffer
    _kernel_event: cl.Event
    _copy_event: cl.Event


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
        device_type: OpenCLDeviceType | None = None,
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
        self._device_type = device_type
        self.last_kernel_seconds = 0.0
        self.last_transfer_seconds = 0.0
        self._sample_buffer_pool: list[tuple[int, cl.Buffer]] = []
        self._scores_buffer_pool: list[tuple[int, cl.Buffer]] = []

    @staticmethod
    def available_device() -> tuple[str, str]:
        device = _select_device()
        return device.platform.name, device.name

    @staticmethod
    def recommend_for_device(
        device_type: OpenCLDeviceType,
        dataset_size: int = 50_000,
        kernel: cl.Kernel | None = None,
        device: cl.Device | None = None,
    ) -> dict[str, int | str]:
        try:
            if device is None or kernel is None:
                executor = OpenCLIsolationForestExecutor(device_type=device_type)
                _, _, selected_kernel, selected_device = executor._get_runtime()
                device = selected_device
                kernel = selected_kernel

            preferred = int(
                kernel.get_work_group_info(
                    cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE,
                    device,
                )
            )
            max_kernel = int(
                kernel.get_work_group_info(
                    cl.kernel_work_group_info.WORK_GROUP_SIZE, device
                )
            )
            max_work_group = min(
                int(device.max_work_group_size),
                max_kernel,
            )
            if preferred < 1:
                preferred = 32 if bool(device.type & cl.device_type.GPU) else 1

            compute_units = int(getattr(device, "max_compute_units", 1) or 1)
            is_gpu = bool(device.type & cl.device_type.GPU)
            if is_gpu:
                base = preferred if preferred >= 32 else 32
                work_group = min(
                    max_work_group,
                    max(64, base * max(1, 64 // max(base, 1))),
                )
                work_group = _align_work_group(work_group, preferred, max_work_group)
                chunk = max(100_000, dataset_size)
                chunk = min(chunk, max(dataset_size, 100_000))
            else:
                target_groups = max(4, 4 * compute_units)
                work_group = preferred if preferred > 0 else 1
                while (
                    work_group * 16 * target_groups < dataset_size
                    and work_group < max_work_group
                ):
                    work_group = _align_work_group(
                        work_group + preferred,
                        preferred,
                        max_work_group,
                    )
                if work_group > max_work_group:
                    work_group = max_work_group
                chunk = compute_units * work_group * 16
                chunk = max(8_000, min(dataset_size or 50_000, chunk))
                if dataset_size and dataset_size < chunk:
                    chunk = dataset_size

            return {
                "work_group_recomendado": max(1, work_group),
                "chunk_recomendado": max(1, chunk),
                "preferred_work_group_multiple": preferred,
                "max_compute_units": compute_units,
                "local_mem_size": int(getattr(device, "local_mem_size", 0) or 0),
                "max_work_group_size": max_work_group,
            }
        except Exception as error:
            logger.warning(
                "Não foi possível calcular recomendação para %s: %s",
                device_type,
                error,
            )
            return {
                "work_group_recomendado": 1,
                "chunk_recomendado": 50_000,
                "preferred_work_group_multiple": 1,
                "max_compute_units": 1,
                "local_mem_size": 0,
                "max_work_group_size": 1,
            }

    @staticmethod
    def available_devices() -> list[tuple[OpenCLDeviceType, str, str, int]]:
        available: list[tuple[OpenCLDeviceType, str, str, int]] = []
        for device_type in ("CPU", "GPU"):
            try:
                executor = OpenCLIsolationForestExecutor(device_type=device_type)
                _, _, kernel, device = executor._get_runtime()
                try:
                    kernel_max_size = kernel.get_work_group_info(
                        cl.kernel_work_group_info.WORK_GROUP_SIZE, device
                    )
                    max_work_group_size = min(
                        int(device.max_work_group_size), int(kernel_max_size)
                    )
                except Exception as error:
                    logger.warning(
                        "Não foi possível consultar o work-group de %s: %s",
                        device.name,
                        error,
                    )
                    continue
                available.append(
                    (
                        device_type,
                        device.platform.name,
                        device.name,
                        max_work_group_size,
                    )
                )
            except Exception as error:
                logger.info(
                    "Dispositivo OpenCL %s indisponível: %s", device_type, error
                )
        return available

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
        pending = self.submit_opencl(
            features,
            work_group_size=work_group_size,
        )
        return self.collect_opencl(pending)

    def _claim_buffer(
        self,
        pool: list[tuple[int, cl.Buffer]],
        capacity_bytes: int,
        context: cl.Context,
        flags: cl.mem_flags,
    ) -> cl.Buffer:
        for index, (capacity, buffer) in enumerate(pool):
            if capacity >= capacity_bytes:
                pool.pop(index)
                return buffer
        return cl.Buffer(context, flags, size=capacity_bytes)

    def submit_opencl(
        self,
        features: NDArray[np.number],
        *,
        work_group_size: int | None = None,
        chunk_id: int = 0,
    ) -> OpenCLPendingResult:
        forest = self._require_fitted()
        matrix = _validate_matrix(
            features, expected_features=self._model.n_features_in_
        )
        if matrix.shape[0] == 0:
            raise ValueError("O bloco de pontuação não pode estar vazio")

        context, queue, kernel, device = self._get_runtime()
        local_size = self._validate_work_group_size(work_group_size, kernel, device)
        samples = np.ascontiguousarray(matrix, dtype=np.float32)
        if not np.isfinite(samples).all():
            raise ValueError("As features excedem o intervalo suportado pelo OpenCL")
        scores = np.empty(samples.shape[0], dtype=np.float32)
        memory_flags = cl.mem_flags

        try:
            forest_buffers = self._get_forest_buffers(context, forest)
            sample_buffer = self._claim_buffer(
                self._sample_buffer_pool,
                samples.nbytes,
                context,
                memory_flags.READ_ONLY,
            )
            scores_buffer = self._claim_buffer(
                self._scores_buffer_pool,
                scores.nbytes,
                context,
                memory_flags.WRITE_ONLY,
            )
            copy_samples_event = cl.enqueue_copy(
                queue,
                sample_buffer,
                samples,
                is_blocking=False,
            )

            global_size = samples.shape[0]
            if local_size is not None:
                global_size = (
                    (global_size + local_size - 1) // local_size
                ) * local_size
            kernel_event = kernel(
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
                wait_for=[copy_samples_event],
            )
            copy_event = cl.enqueue_copy(
                queue,
                scores,
                scores_buffer,
                is_blocking=False,
                wait_for=[kernel_event],
            )
        except cl.Error as error:
            raise OpenCLExecutionError(
                f"Falha ao executar a pontuação Isolation Forest em OpenCL: {error}"
            ) from error
        return OpenCLPendingResult(
            scores=scores,
            chunk_id=chunk_id,
            _sample_buffer=sample_buffer,
            _scores_buffer=scores_buffer,
            _kernel_event=kernel_event,
            _copy_event=copy_event,
        )

    def collect_opencl(self, pending: OpenCLPendingResult) -> NDArray[np.float32]:
        if pending._copy_event is None or pending._kernel_event is None:
            return pending.scores
        try:
            pending._copy_event.wait()
            pending._kernel_event.wait()
            if (
                pending._kernel_event.profile.end > 0
                and pending._kernel_event.profile.start > 0
            ):
                self.last_kernel_seconds = (
                    pending._kernel_event.profile.end
                    - pending._kernel_event.profile.start
                ) / 1_000_000_000.0
            if (
                pending._copy_event.profile.end > 0
                and pending._copy_event.profile.start > 0
            ):
                self.last_transfer_seconds = (
                    pending._copy_event.profile.end - pending._copy_event.profile.start
                ) / 1_000_000_000.0
        except cl.Error as error:
            raise OpenCLExecutionError(
                f"Falha ao aguardar a pontuação Isolation Forest em OpenCL: {error}"
            ) from error
        finally:
            if len(self._sample_buffer_pool) < 3:
                self._sample_buffer_pool.append(
                    (pending._sample_buffer.size, pending._sample_buffer)
                )
            if len(self._scores_buffer_pool) < 3:
                self._scores_buffer_pool.append(
                    (pending._scores_buffer.size, pending._scores_buffer)
                )
        return pending.scores

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
        chunk_size: int = 50_000,
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
        total_kernel_seconds = 0.0
        total_transfer_seconds = 0.0
        for chunk_id, start in enumerate(range(0, matrix.shape[0], chunk_size)):
            chunk = matrix[start : start + chunk_size]
            score_chunks.append(
                self.score_opencl(chunk, work_group_size=work_group_size)
            )
            total_kernel_seconds += self.last_kernel_seconds
            total_transfer_seconds += self.last_transfer_seconds
            chunk_id_parts.append(np.full(chunk.shape[0], chunk_id, dtype=np.int32))

        scores = np.concatenate(score_chunks)
        return OpenCLExecutionResult(
            scores=scores,
            suspicious=scores >= threshold,
            chunk_ids=np.concatenate(chunk_id_parts),
            elapsed_seconds=perf_counter() - started,
            tempo_kernel_s=total_kernel_seconds,
            tempo_transferencia_s=total_transfer_seconds,
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

        device = _select_device(self._device_type)
        try:
            context = cl.Context(devices=[device])
            queue = cl.CommandQueue(
                context,
                device=device,
                properties=cl.command_queue_properties.PROFILING_ENABLE,
            )
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
        is_cpu = bool(device.type & cl.device_type.CPU)
        if is_cpu:
            try:
                preferred = int(
                    kernel.get_work_group_info(
                        cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE,
                        device,
                    )
                )
            except cl.Error:
                preferred = 1
            compute_units = int(getattr(device, "max_compute_units", 1) or 1)
            maximum = min(int(device.max_work_group_size), int(max_kernel_size))
            return _balance_local_size(
                work_group_size,
                preferred,
                compute_units,
                maximum,
            )
        return work_group_size

    def _require_fitted(self) -> _ForestArrays:
        if self._forest is None:
            raise RuntimeError("O executor precisa ser ajustado antes da pontuação")
        return self._forest


def _align_work_group(value: int, multiple: int, maximum: int) -> int:
    if multiple <= 1:
        return min(max(value, 1), maximum)
    aligned = max(multiple, ((value + multiple - 1) // multiple) * multiple)
    return min(aligned, maximum)


def available_cpu_capacity() -> int:
    affinity_capacity: int | None = None
    try:
        affinity_capacity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity_capacity = os.cpu_count()

    cgroup_capacity: int | None = None
    try:
        with open("/sys/fs/cgroup/cpu.max", encoding="ascii") as cpu_max:
            quota_text, period_text = cpu_max.read().strip().split()
        if quota_text != "max":
            quota = int(quota_text)
            period = int(period_text)
            if quota > 0 and period > 0:
                cgroup_capacity = max(1, (quota + period - 1) // period)
    except (FileNotFoundError, OSError, ValueError):
        try:
            with open(
                "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
                encoding="ascii",
            ) as quota_file:
                quota = int(quota_file.read().strip())
            with open(
                "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
                encoding="ascii",
            ) as period_file:
                period = int(period_file.read().strip())
            if quota > 0 and period > 0:
                cgroup_capacity = max(1, (quota + period - 1) // period)
        except (FileNotFoundError, OSError, ValueError):
            pass

    capacities = [
        capacity
        for capacity in (affinity_capacity, cgroup_capacity)
        if capacity is not None and capacity > 0
    ]
    return min(capacities) if capacities else 1


def _balance_local_size(
    work_group_size: int,
    preferred_multiple: int,
    max_compute_units: int,
    max_work_group_size: int,
) -> int:
    if work_group_size < 1:
        work_group_size = 1
    preferred = max(1, preferred_multiple)
    maximum = max(1, max_work_group_size)
    compute_units = max(1, max_compute_units)
    minimum_multiple = preferred
    balanced_limit = max(minimum_multiple, maximum // max(4 * compute_units, 1))
    requested = min(work_group_size, maximum)
    if requested <= balanced_limit:
        return _align_work_group(requested, preferred, maximum)
    return _align_work_group(balanced_limit, preferred, maximum)


def _get_platforms() -> list[cl.Platform]:
    try:
        return cl.get_platforms()
    except Exception as error:
        raise OpenCLRuntimeUnavailableError(
            "Nenhuma plataforma OpenCL está disponível neste ambiente"
        ) from error


def _select_device(device_type: OpenCLDeviceType | None = None) -> cl.Device:
    platforms = _get_platforms()
    devices: list[cl.Device] = []
    errors: list[str] = []
    for platform in platforms:
        try:
            devices.extend(platform.get_devices())
        except Exception as error:
            errors.append(f"{platform.name}: {error}")

    if not devices:
        detail = "; ".join(errors) if errors else "nenhum dispositivo foi listado"
        raise OpenCLRuntimeUnavailableError(
            "Nenhum dispositivo OpenCL está disponível. Instale um runtime "
            f"OpenCL compatível com o hardware. Detalhes: {detail}"
        )

    if device_type == "CPU":
        devices = [device for device in devices if device.type & cl.device_type.CPU]
    elif device_type == "GPU":
        devices = [device for device in devices if device.type & cl.device_type.GPU]
    if device_type is not None and not devices:
        raise OpenCLRuntimeUnavailableError(
            f"Nenhum dispositivo {device_type} OpenCL está disponível."
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
