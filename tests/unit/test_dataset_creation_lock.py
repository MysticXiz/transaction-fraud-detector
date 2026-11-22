from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from src.fraud_detector.api.routes import analyses, benchmarks
from src.fraud_detector.api.schemas.analysis import CriarExecucaoSchema
from src.fraud_detector.api.schemas.benchmark import CriarBenchmarkSchema
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.infrastructure.models.dataset import DatasetModel


@pytest.mark.parametrize("kind", ["analysis", "benchmark"])
@pytest.mark.parametrize("count", [1, 2])
def test_creation_locks_before_validating_dataset_count(monkeypatch, kind, count):
    db = Session()
    dataset = DatasetModel(id_dataset=5, id_usuario=7, total_registros=count)
    model = SimpleNamespace(
        id_modelo=2, algoritmo=TipoAlgoritmo.ISOLATION_FOREST, limiar_padrao=None
    )
    user = SimpleNamespace(id_usuario=7)
    events = []

    def execute(statement, *args, **kwargs):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        if "FROM dataset" in sql:
            assert "dataset.id_usuario =" in sql
            assert "dataset.id_dataset =" in sql
            if not events:
                assert "FOR UPDATE OF dataset" in sql
                assert kwargs["execution_options"][
                    "_sa_orm_load_options"
                ]._populate_existing
                events.append("lock")
            else:
                assert events == ["lock"]
                events.append("dataset read")
            row = dataset
        else:
            assert "FROM modelo_deteccao" in sql
            assert events[0] == "lock"
            events.append("model read")
            row = model
        result = MagicMock()
        result._attributes = {"is_single_entity": True}
        result.scalars.return_value._attributes = {}
        result.scalars.return_value.first.return_value = row
        return result

    monkeypatch.setattr(db, "execute", execute)
    monkeypatch.setattr(db, "add", lambda record: events.append("add"))
    monkeypatch.setattr(db, "commit", lambda: events.append("commit"))
    monkeypatch.setattr(db, "refresh", lambda record: None)
    monkeypatch.setattr(analyses, "_execution_response", lambda *args: None)
    monkeypatch.setattr(benchmarks, "_benchmark_response", lambda *args: None)

    mode = ModoExecucao.SEQUENCIAL
    if kind == "analysis":
        handler = analyses.create_analysis
        payload = CriarExecucaoSchema(id_dataset=5, id_modelo=2, modo_execucao=mode)
    else:
        handler = benchmarks.create_benchmark
        payload = CriarBenchmarkSchema(
            id_dataset=5,
            id_modelo=2,
            configuracoes=[{"modo_execucao": mode, "rotulo": "baseline"}],
        )

    if count < 2:
        with pytest.raises(HTTPException) as error:
            handler(payload, user, db)
        assert error.value.status_code == 422
        assert "ao menos duas transações" in error.value.detail
        assert "add" not in events and "commit" not in events
    else:
        handler(payload, user, db)
        assert events[-2:] == ["add", "commit"]
    assert events[0] == "lock"
