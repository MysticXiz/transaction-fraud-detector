import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.fraud_detector.computational.ingestion.dataset_csv import (
    DatasetImportCancelledError,
)
from src.fraud_detector.infrastructure.database.database import engine
from src.fraud_detector.infrastructure.models.dataset_import_job import (
    DatasetImportJobModel,
)

logger = logging.getLogger(__name__)

_RUNNING = ("RECEBENDO", "PROCESSANDO")
_ACTIVE = (*_RUNNING, "CANCELAMENTO_SOLICITADO")
_INTERRUPTED = "Importação interrompida. Inicie uma nova importação."
_CANCELLED = "A importação foi cancelada"
_TRY_UPLOAD_LOCK = text("SELECT pg_try_advisory_lock(174903541, :job_id)")
_UNLOCK_UPLOAD = text("SELECT pg_advisory_unlock(174903541, :job_id)")
_TRY_RECOVERY_LOCK = text("SELECT pg_try_advisory_xact_lock(174903541, :job_id)")


@contextmanager
def try_import_upload(import_id: int) -> Iterator[Session | None]:
    # Use the same physical connection for the lock and COPY. A session lock
    # survives the commits that publish RECEBENDO and PROCESSANDO.
    with engine.connect() as connection:
        params = {"job_id": import_id}
        try:
            acquired = connection.scalar(_TRY_UPLOAD_LOCK, params)
            connection.commit()
        except Exception:
            connection.invalidate()
            raise
        if not acquired:
            yield None
            return
        try:
            with Session(bind=connection) as db:
                yield db
        finally:
            if not connection.invalidated:
                try:
                    connection.scalar(_UNLOCK_UPLOAD, params)
                    connection.commit()
                except Exception:
                    # Never put a connection with a possibly held lock back in the pool.
                    connection.invalidate()
                    logger.exception(
                        "Falha ao liberar o lock da importação %s", import_id
                    )


class RepositorioImportacaoDataset:
    def __init__(self, db: Session, import_id: int, owner_id: int):
        self.db = db
        self.import_id = import_id
        self.owner_id = owner_id

    def get(self, *, lock: bool = False) -> DatasetImportJobModel | None:
        stmt = select(DatasetImportJobModel).where(
            DatasetImportJobModel.id_importacao == self.import_id,
            DatasetImportJobModel.id_usuario == self.owner_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt.execution_options(populate_existing=True))

    def get_with_recovery(self) -> DatasetImportJobModel | None:
        job = self.get()
        if job is None or job.status not in _ACTIVE or not self._try_idle_lock():
            return job
        job = self.get(lock=True)
        if job is not None and job.status in _ACTIVE:
            self._finish_error(job, _INTERRUPTED)
        return job

    def cancel(self, job: DatasetImportJobModel) -> None:
        if job.status == "PENDENTE":
            job.status = "CANCELADO"
        elif job.status in _ACTIVE:
            job.cancelamento_solicitado = True
            if self._try_idle_lock():
                self._finish_error(job, _CANCELLED)
            else:
                job.status = "CANCELAMENTO_SOLICITADO"

    def begin_processing(self) -> None:
        job = self._require_running("RECEBENDO")
        job.status = "PROCESSANDO"
        self.db.commit()

    def stage_completion(self, dataset_id: int) -> None:
        job = self._require_running("PROCESSANDO")
        job.status = "CONCLUIDO"
        job.id_dataset = dataset_id
        job.mensagem_erro = None

    def finish_error(self, message: str) -> bool:
        job = self.get(lock=True)
        if job is not None and job.status in _ACTIVE:
            self._finish_error(job, message)
        return job is not None and job.status == "CANCELADO"

    def _require_running(self, status: str) -> DatasetImportJobModel:
        job = self.get(lock=True)
        if job is None or job.status != status or job.cancelamento_solicitado:
            raise DatasetImportCancelledError(_CANCELLED)
        return job

    def _try_idle_lock(self) -> bool:
        return bool(self.db.scalar(_TRY_RECOVERY_LOCK, {"job_id": self.import_id}))

    @staticmethod
    def _finish_error(job: DatasetImportJobModel, message: str) -> None:
        if job.cancelamento_solicitado or job.status == "CANCELAMENTO_SOLICITADO":
            job.status = "CANCELADO"
            job.mensagem_erro = _CANCELLED
        else:
            job.status = "FALHA"
            job.mensagem_erro = message
