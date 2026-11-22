from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from src.fraud_detector.api.routes import transactions
from src.fraud_detector.api.schemas.transaction import (
    TransacaoAtualizacaoSchema,
    TransacaoCriacaoSchema,
)
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel
from src.fraud_detector.infrastructure.repositories.transaction_repository import (
    RepositorioTransacao,
)


@pytest.fixture
def mutation(monkeypatch):
    db = Session()
    dataset = DatasetModel(id_dataset=5, id_usuario=7, total_registros=99)
    transaction = TransacaoModel(
        id_transacao=3, id_dataset=5, indice_origem=4, valor=Decimal("10"), atributos={}
    )
    state = SimpleNamespace(
        dataset=dataset,
        transaction=transaction,
        target=dataset,
        history=False,
        count=2,
        events=[],
    )

    def execute(statement, *args, **kwargs):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        result = MagicMock()
        result._attributes = {"is_single_entity": True}
        result.scalars.return_value._attributes = {}
        if "FOR UPDATE OF dataset" in sql:
            assert "dataset.id_usuario =" in sql
            state.events.append("lock")
            result.scalars.return_value.first.return_value = state.target
        elif "EXISTS" in sql:
            assert "execucao_analise.id_dataset =" in sql
            assert "benchmark.id_dataset =" in sql
            assert "status" not in sql
            state.events.append("history")
            result._attributes = {}
            result.one.return_value = (state.history,)
        elif "count(" in sql:
            assert "transacao.id_dataset =" in sql
            state.events.append("count")
            result._attributes = {}
            result.one.return_value = (state.count,)
        else:
            assert "WHERE transacao.id_transacao =" in sql
            assert "transacao.id_dataset =" in sql
            state.events.append("reload")
            result.scalars.return_value.first.return_value = state.transaction
        return result

    def add(model):
        state.events.append("add")
        model.id_transacao = 8

    monkeypatch.setattr(db, "execute", execute)
    monkeypatch.setattr(db, "add", add)
    for method in ("delete", "flush", "refresh", "commit", "rollback"):
        monkeypatch.setattr(
            db, method, lambda *args, method=method: state.events.append(method)
        )

    def call(operation):
        repo = RepositorioTransacao(db)
        user = SimpleNamespace(id_usuario=7)
        if operation == "create":
            return transactions.create_transaction(
                TransacaoCriacaoSchema(id_dataset=5, indice_origem=6), user, repo
            )
        if operation == "update":
            return transactions.update_transaction(
                3, TransacaoAtualizacaoSchema(valor=Decimal("15")), user, repo
            )
        return transactions.delete_transaction(3, user, repo)

    return state, call, db


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_referenced_dataset_rejects_mutation_and_rolls_back(mutation, operation):
    state, call, _ = mutation
    state.history = True

    with pytest.raises(HTTPException) as error:
        call(operation)

    assert error.value.status_code == 409
    reload = [] if operation == "create" else ["reload"]
    assert state.events == ["lock", *reload, "history", "rollback"]
    assert state.dataset.total_registros == 99
    assert state.transaction.valor == 10


@pytest.mark.parametrize(
    ("operation", "count", "events"),
    [
        (
            "create",
            3,
            ["lock", "history", "add", "flush", "count", "refresh", "commit"],
        ),
        (
            "update",
            2,
            ["lock", "reload", "history", "flush", "count", "refresh", "commit"],
        ),
        (
            "delete",
            0,
            ["lock", "reload", "history", "delete", "flush", "count", "commit"],
        ),
    ],
)
def test_successful_mutation_recounts_before_commit(mutation, operation, count, events):
    state, call, _ = mutation
    state.count = count

    result = call(operation)

    assert state.dataset.total_registros == count
    assert state.events == events
    if operation == "create":
        assert result.id_transacao == 8
    elif operation == "update":
        assert result.valor == 15


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_transaction_deleted_while_waiting_for_lock_returns_404(mutation, operation):
    state, call, _ = mutation
    state.transaction = None
    state.history = True

    with pytest.raises(HTTPException) as error:
        call(operation)

    assert error.value.status_code == 404
    assert state.events == ["lock", "reload", "commit"]


def test_commit_failure_rolls_back_mutation_and_count_together(mutation, monkeypatch):
    state, call, db = mutation

    def fail_commit():
        assert state.dataset.total_registros == 2
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="commit failed"):
        call("delete")

    assert state.events == [
        "lock",
        "reload",
        "history",
        "delete",
        "flush",
        "count",
        "rollback",
    ]
