import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLIsolationForestExecutor,
    OpenCLRuntimeUnavailableError,
    _average_path_length,
    _pack_forest,
)


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
