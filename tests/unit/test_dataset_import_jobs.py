from contextlib import nullcontext
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.dialects import postgresql

from src.fraud_detector.api.routes import datasets
from src.fraud_detector.infrastructure.models.dataset_import_job import (
    DatasetImportJobModel,
)
from src.fraud_detector.infrastructure.repositories import (
    dataset_import_repository as import_repository,
    dataset_repository,
)


def make_job(status="PENDENTE"):
    return DatasetImportJobModel(
        id_importacao=5,
        id_usuario=7,
        nome="Sample",
        origem="synthetic",
        nome_arquivo="input.csv",
        status=status,
        cancelamento_solicitado=status == "CANCELAMENTO_SOLICITADO",
    )


@pytest.fixture
def upload(monkeypatch, tmp_path):
    job = make_job()
    db = MagicMock()
    db.scalar.return_value = job
    db.query.return_value.filter.return_value.first.return_value = None
    driver = MagicMock()
    copy = driver.cursor.return_value.__enter__.return_value.copy.return_value
    monkeypatch.setattr(dataset_repository, "_driver_connection", lambda _: driver)
    monkeypatch.setattr(datasets.settings, "dataset_storage_path", tmp_path)
    monkeypatch.setattr(datasets, "get_upload_limit", lambda: 1024)
    monkeypatch.setattr(
        datasets, "_import_cancellation_checker", lambda *_: lambda: False
    )
    commits = []

    def add(dataset):
        dataset.id_dataset = 42
        dataset.importado_em = datetime.now(UTC)

    db.add.side_effect = add
    db.commit.side_effect = lambda: commits.append((job.status, job.id_dataset))
    file = UploadFile(BytesIO(b"Time,Amount\n1,2\n"), filename="input.csv")
    return SimpleNamespace(job=job, db=db, file=file, copy=copy, commits=commits)


def test_import_claim_and_completion_commit_with_copy(upload, tmp_path):
    result = datasets._run_dataset_import(upload.db, 5, 7, upload.file)

    assert result.id_dataset == 42
    assert result.total_registros == 1
    assert upload.commits == [
        ("RECEBENDO", None),
        ("PROCESSANDO", None),
        ("CONCLUIDO", 42),
    ]
    upload.copy.__enter__.return_value.write.assert_called_once()
    assert len(list(tmp_path.glob("*.csv"))) == 1
    for call in upload.db.scalar.call_args_list:
        sql = str(call.args[0].compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql
        assert "dataset_import_job.id_usuario =" in sql


def test_import_duplicate_upload_cannot_enter_claim(monkeypatch, upload):
    monkeypatch.setattr(datasets, "try_import_upload", lambda _: nullcontext(None))

    with pytest.raises(HTTPException) as conflict:
        datasets.upload_dataset_import(
            5, upload.file, SimpleNamespace(id_usuario=7), upload.db
        )

    assert conflict.value.status_code == 409
    assert upload.job.status == "PENDENTE"
    upload.db.commit.assert_not_called()
    upload.db.add.assert_not_called()


@pytest.mark.parametrize("initial_status", ["RECEBENDO", "CANCELADO", "CONCLUIDO"])
def test_import_claim_rechecks_status_under_row_lock(upload, initial_status):
    upload.job.status = initial_status
    upload.file.filename = "invalid.txt"
    with pytest.raises(HTTPException) as conflict:
        datasets._run_dataset_import(upload.db, 5, 7, upload.file)

    assert conflict.value.status_code == 409
    assert upload.job.status == initial_status
    upload.db.commit.assert_not_called()


def test_import_setup_failure_after_claim_does_not_leave_job_receiving(
    monkeypatch, upload
):
    def unavailable_limit():
        raise OSError("upload settings unavailable")

    monkeypatch.setattr(datasets, "get_upload_limit", unavailable_limit)
    with pytest.raises(HTTPException) as failure:
        datasets._run_dataset_import(upload.db, 5, 7, upload.file)

    assert failure.value.status_code == 500
    assert upload.commits == [("RECEBENDO", None), ("FALHA", None)]
    upload.db.add.assert_not_called()


def test_import_late_cancel_rolls_back_copy_even_with_stale_poll(upload, tmp_path):
    def request_cancel(*_):
        upload.job.status = "CANCELAMENTO_SOLICITADO"
        upload.job.cancelamento_solicitado = True

    # Simulate cancellation committed after the last COPY write.
    upload.copy.__exit__.side_effect = request_cancel

    with pytest.raises(HTTPException) as conflict:
        datasets._run_dataset_import(upload.db, 5, 7, upload.file)

    assert conflict.value.status_code == 409
    assert upload.commits == [
        ("RECEBENDO", None),
        ("PROCESSANDO", None),
        ("CANCELADO", None),
    ]
    upload.db.rollback.assert_called()
    assert list(tmp_path.iterdir()) == []


def test_import_unknown_commit_outcome_keeps_artifact_and_terminal_job(
    upload, tmp_path
):
    record_commit = upload.db.commit.side_effect

    def commit_with_lost_acknowledgement():
        record_commit()
        if len(upload.commits) == 3:
            raise OSError("connection lost after commit")

    upload.db.commit.side_effect = commit_with_lost_acknowledgement
    with pytest.raises(HTTPException) as failure:
        datasets._run_dataset_import(upload.db, 5, 7, upload.file)

    assert failure.value.status_code == 500
    assert upload.commits[2:] == [("CONCLUIDO", 42), ("CONCLUIDO", 42)]
    assert len(list(tmp_path.glob("*.csv"))) == 1


@pytest.mark.parametrize(
    ("status", "idle", "expected"),
    [
        ("PENDENTE", True, "PENDENTE"),
        ("RECEBENDO", False, "RECEBENDO"),
        ("PROCESSANDO", True, "FALHA"),
        ("CANCELAMENTO_SOLICITADO", True, "CANCELADO"),
    ],
)
def test_import_poll_recovers_only_when_upload_is_gone(status, idle, expected):
    job = make_job(status)
    db = MagicMock()
    db.scalar.side_effect = [job, idle, job]

    response = datasets.get_dataset_import(5, SimpleNamespace(id_usuario=7), db)

    assert response.status == expected
    db.commit.assert_called_once()
    if status == "PENDENTE":
        db.scalar.assert_called_once()
    else:
        stmt = db.scalar.call_args_list[1].args[0]
        assert "pg_try_advisory_xact_lock" in str(stmt)


def test_import_recovery_rereads_job_that_completed_before_lock():
    completed = make_job("CONCLUIDO")
    completed.id_dataset = 42
    db = MagicMock()
    db.scalar.side_effect = [make_job("PROCESSANDO"), True, completed]

    response = datasets.get_dataset_import(5, SimpleNamespace(id_usuario=7), db)

    assert response.status == "CONCLUIDO"
    assert response.id_dataset == 42
    assert "FOR UPDATE" in str(db.scalar.call_args_list[2].args[0])


@pytest.mark.parametrize(
    ("status", "idle", "expected"),
    [
        ("PENDENTE", True, "CANCELADO"),
        ("PROCESSANDO", False, "CANCELAMENTO_SOLICITADO"),
        ("RECEBENDO", True, "CANCELADO"),
        ("CONCLUIDO", True, "CONCLUIDO"),
    ],
)
def test_import_cancel_preserves_completed_jobs(status, idle, expected):
    job = make_job(status)
    db = MagicMock()
    db.scalar.side_effect = [job, idle]

    response = datasets.cancel_dataset_import(5, SimpleNamespace(id_usuario=7), db)

    assert response.status == expected
    assert "FOR UPDATE" in str(db.scalar.call_args_list[0].args[0])
    db.commit.assert_called_once()


def test_import_upload_lock_releases_on_handler_error(monkeypatch):
    connection = MagicMock(invalidated=False)
    connection.scalar.return_value = True
    monkeypatch.setattr(
        import_repository,
        "engine",
        SimpleNamespace(connect=lambda: nullcontext(connection)),
    )

    with pytest.raises(RuntimeError, match="handler failed"):
        with import_repository.try_import_upload(5) as db:
            assert db.bind is connection
            raise RuntimeError("handler failed")

    assert [str(call.args[0]) for call in connection.scalar.call_args_list] == [
        "SELECT pg_try_advisory_lock(174903541, :job_id)",
        "SELECT pg_advisory_unlock(174903541, :job_id)",
    ]
