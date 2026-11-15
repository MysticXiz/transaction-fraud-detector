import numpy as np
import pytest
from sklearn.ensemble import IsolationForest
from types import SimpleNamespace

from src.fraud_detector.computational.execution import opencl_isolation_forest
from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLIsolationForestExecutor,
    OpenCLRuntimeUnavailableError,
    _average_path_length,
    _balance_local_size,
    _pack_forest,
)


def test_balance_local_size_keeps_multiple_work_groups_per_compute_unit():
    balanced = _balance_local_size(
        work_group_size=512,
        preferred_multiple=16,
        max_compute_units=6,
        max_work_group_size=4096,
    )

    assert balanced == 176
    assert balanced % 16 == 0


def test_select_device_can_target_cpu_or_gpu(monkeypatch):
    cpu = SimpleNamespace(type=opencl_isolation_forest.cl.device_type.CPU, name="CPU")
    gpu = SimpleNamespace(type=opencl_isolation_forest.cl.device_type.GPU, name="GPU")
    platform = SimpleNamespace(
        name="Test platform",
        get_devices=lambda: [cpu, gpu],
    )
    monkeypatch.setattr(opencl_isolation_forest, "_get_platforms", lambda: [platform])

    assert opencl_isolation_forest._select_device("CPU") is cpu
    assert opencl_isolation_forest._select_device("GPU") is gpu


def make_transactions() -> np.ndarray:
    random = np.random.default_rng(42)
    normal = random.normal(0.0, 1.0, size=(95, 4))
    outliers = random.normal(8.0, 0.3, size=(5, 4))
    return np.ascontiguousarray(np.vstack((normal, outliers)), dtype=np.float64)


def test_packed_forest_retains_tree_features_and_leaf_path_lengths():
    transactions = make_transactions()
    model = IsolationForest(
        n_estimators=11,
        max_samples="auto",
        contamination=0.05,
        random_state=42,
        n_jobs=1,
    ).fit(transactions)

    packed = _pack_forest(model)

    assert packed.children_left.shape == (11, packed.max_nodes)
    assert packed.children_right.shape == packed.children_left.shape
    assert packed.features.shape == packed.children_left.shape
    assert packed.thresholds.shape == packed.children_left.shape
    assert packed.leaf_path_lengths.shape == packed.children_left.shape
    assert packed.feature_indices.shape == (11, packed.features_per_tree)
    for tree_id, selected_features in enumerate(model.estimators_features_):
        leaves = packed.children_left[tree_id] < 0
        assert leaves.any()
        assert np.isfinite(packed.leaf_path_lengths[tree_id, leaves]).all()
        assert (packed.leaf_path_lengths[tree_id, leaves] >= 0).all()
        np.testing.assert_array_equal(
            packed.feature_indices[tree_id, : len(selected_features)],
            selected_features,
        )
    assert packed.denominator > 0
    assert _average_path_length(1) == 0
    assert _average_path_length(2) == 1


def test_sequential_reference_matches_sklearn_scores():
    transactions = make_transactions()
    executor = OpenCLIsolationForestExecutor(
        n_estimators=25, contamination=0.05, random_state=42
    ).fit(transactions)

    np.testing.assert_allclose(
        executor.score_sequential(transactions),
        -executor._model.score_samples(transactions),
        rtol=0,
        atol=0,
    )


def test_execute_rejects_invalid_configuration_before_device_access():
    executor = OpenCLIsolationForestExecutor(n_estimators=5)

    with pytest.raises(ValueError, match="limiar"):
        executor.execute(make_transactions(), threshold=1.1)
    with pytest.raises(ValueError, match="bloco"):
        executor.execute(make_transactions(), chunk_size=0)


def test_opencl_scores_match_sequential_and_preserve_chunk_order():
    transactions = make_transactions()
    executor = OpenCLIsolationForestExecutor(
        n_estimators=25, contamination=0.05, random_state=42
    ).fit(transactions)
    try:
        executor.available_device()
    except OpenCLRuntimeUnavailableError as error:
        pytest.skip(str(error))

    sequential_scores = executor.score_sequential(transactions)
    opencl_scores = executor.score_opencl(transactions, work_group_size=8)
    np.testing.assert_allclose(opencl_scores, sequential_scores, rtol=2e-5, atol=2e-5)

    result = OpenCLIsolationForestExecutor(
        n_estimators=25, contamination=0.05, random_state=42
    ).execute(transactions, threshold=0.5, chunk_size=13, work_group_size=8)
    np.testing.assert_allclose(result.scores, sequential_scores, rtol=2e-5, atol=2e-5)
    np.testing.assert_array_equal(result.suspicious, sequential_scores >= 0.5)
    np.testing.assert_array_equal(
        result.chunk_ids,
        np.repeat(np.arange(8, dtype=np.int32), [13] * 7 + [9]),
    )


def test_get_platforms_treats_platform_not_found_as_runtime_unavailable(monkeypatch):
    def fail():
        raise RuntimeError("PLATFORM_NOT_FOUND_KHR")

    monkeypatch.setattr(opencl_isolation_forest.cl, "get_platforms", fail)

    with pytest.raises(OpenCLRuntimeUnavailableError):
        opencl_isolation_forest._get_platforms()


def test_available_devices_returns_only_detected_devices(monkeypatch):
    cpu = SimpleNamespace(
        type=opencl_isolation_forest.cl.device_type.CPU,
        name="CPU teste",
        platform=SimpleNamespace(name="PoCL"),
        max_work_group_size=256,
    )
    gpu = SimpleNamespace(
        type=opencl_isolation_forest.cl.device_type.GPU,
        name="GPU teste",
        platform=SimpleNamespace(name="CUDA teste"),
        max_work_group_size=1024,
    )

    class FakeKernel:
        def get_work_group_info(self, _info, device):
            return 256

    def fake_runtime(self):
        device = cpu if self._device_type == "CPU" else gpu
        return object(), object(), FakeKernel(), device

    monkeypatch.setattr(
        OpenCLIsolationForestExecutor,
        "_get_runtime",
        fake_runtime,
    )

    assert OpenCLIsolationForestExecutor.available_devices() == [
        ("CPU", "PoCL", "CPU teste", 256),
        ("GPU", "CUDA teste", "GPU teste", 256),
    ]


def test_recommend_for_cpu_uses_real_device_limits(monkeypatch):
    cpu = SimpleNamespace(
        type=opencl_isolation_forest.cl.device_type.CPU,
        max_work_group_size=256,
        max_compute_units=6,
        local_mem_size=32_768,
        platform=SimpleNamespace(name="PoCL"),
        name="CPU teste",
    )

    class FakeKernel:
        def get_work_group_info(self, info, device):
            if (
                info
                == opencl_isolation_forest.cl.kernel_work_group_info.WORK_GROUP_SIZE
            ):
                return 256
            return 16

    monkeypatch.setattr(
        OpenCLIsolationForestExecutor,
        "_get_runtime",
        lambda self: (object(), object(), FakeKernel(), cpu),
    )

    recommendation = OpenCLIsolationForestExecutor.recommend_for_device(
        "CPU",
        dataset_size=100_000,
    )

    assert 1 <= recommendation["work_group_recomendado"] <= 256
    assert recommendation["chunk_recomendado"] > 0
    assert recommendation["preferred_work_group_multiple"] == 16
    assert recommendation["max_compute_units"] == 6


def test_available_devices_ignores_work_group_query_failure(monkeypatch):
    cpu = SimpleNamespace(
        type=opencl_isolation_forest.cl.device_type.CPU,
        name="CPU teste",
        platform=SimpleNamespace(name="PoCL"),
        max_work_group_size=256,
    )

    class BrokenKernel:
        def get_work_group_info(self, _info, device):
            raise RuntimeError("falha simulada")

    def fake_runtime(self):
        if self._device_type == "GPU":
            raise OpenCLRuntimeUnavailableError("GPU inexistente")
        return object(), object(), BrokenKernel(), cpu

    monkeypatch.setattr(
        OpenCLIsolationForestExecutor,
        "_get_runtime",
        fake_runtime,
    )

    assert OpenCLIsolationForestExecutor.available_devices() == []
