from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.fraud_detector.application import analysis_service
from src.fraud_detector.domain.enums.execution_status import StatusExecucao


def _row(**attributes):
    return SimpleNamespace(
        id_transacao=1, tempo_relativo=0, valor=5, atributos=attributes
    )


def test_matrix_budget_checks_row_growth_with_unchanged_columns():
    budget = analysis_service._AnalysisMatrixBudget(2_000)
    budget.reserve_rows([_row(V1=1), _row(V1=2)])
    with pytest.raises(analysis_service.AnalysisMatrixLimitError, match="matriz"):
        budget.reserve_rows([_row(V1=3), _row(V1=4)])


def test_matrix_budget_accounts_for_object_payload():
    budget = analysis_service._AnalysisMatrixBudget(4_000)
    rows = [_row(note="x" * 5_000)]
    budget.reserve_rows(rows)
    frame = analysis_service._transactions_frame(rows)
    with pytest.raises(analysis_service.AnalysisMatrixLimitError, match="matriz"):
        budget.account_objects(frame)


def test_execution_does_not_materialize_an_over_budget_partition(monkeypatch):
    monkeypatch.setattr(
        analysis_service.settings, "analysis_matrix_memory_limit_bytes", 2_400
    )
    db = MagicMock()
    execution = SimpleNamespace(status=StatusExecucao.PENDENTE, id_dataset=1)
    db.query.return_value.filter_by.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = (
        execution
    )
    first = [_row(V1=1), _row(V1=2)]
    second = [_row(V2=3)]
    db.execute.return_value.__enter__.return_value.partitions.return_value = iter(
        [first, second]
    )
    build_frame = MagicMock(wraps=analysis_service._transactions_frame)
    monkeypatch.setattr(analysis_service, "_transactions_frame", build_frame)
    concat = MagicMock()
    monkeypatch.setattr(analysis_service.pd, "concat", concat)
    monkeypatch.setattr(analysis_service, "_save_metrics", MagicMock())

    analysis_service.run_execution(db, 1)

    build_frame.assert_called_once_with(first, measure_columns=(0, 1))
    concat.assert_not_called()
    assert execution.status == StatusExecucao.FALHA
