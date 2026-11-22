import pytest

from src.fraud_detector.application.execution_errors import (
    ANALYSIS_FAILED,
    BENCHMARK_FAILED,
    EXECUTION_INTERRUPTED,
    MATRIX_LIMIT_EXCEEDED,
    public_execution_error,
)


@pytest.mark.parametrize("fallback", [ANALYSIS_FAILED, BENCHMARK_FAILED])
def test_diagnostics_from_older_executions_are_not_exposed(fallback):
    assert (
        public_execution_error("SQL driver error with private row data", fallback)
        == fallback
    )


@pytest.mark.parametrize(
    "message", [None, MATRIX_LIMIT_EXCEEDED, EXECUTION_INTERRUPTED]
)
def test_safe_execution_messages_remain_actionable(message):
    assert public_execution_error(message, ANALYSIS_FAILED) == message
