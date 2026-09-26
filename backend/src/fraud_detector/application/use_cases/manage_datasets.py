import logging
from pathlib import Path
from time import perf_counter
from typing import BinaryIO
from uuid import uuid4

from src.fraud_detector.computational.ingestion.dataset_csv import (
    DatasetCsvReader,
    stream_upload_to_file,
)
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel
from src.fraud_detector.infrastructure.repositories.dataset_repository import RepositorioDataset

logger = logging.getLogger("fraud_detector.datasets")


class ImportarDatasetUseCase:
    def __init__(
        self,
        repository: RepositorioDataset,
        storage_path: Path,
        *,
        max_upload_bytes: int,
        chunk_bytes: int = 1_048_576,
        copy_buffer_bytes: int = 1_048_576,
        progress_every_rows: int = 50_000,
    ):
        self.repository = repository
        self.storage_path = storage_path
        self.max_upload_bytes = max_upload_bytes
        self.chunk_bytes = chunk_bytes
        self.copy_buffer_bytes = copy_buffer_bytes
        self.progress_every_rows = progress_every_rows

    def execute(
        self,
        stream: BinaryIO,
        filename: str,
        owner_id: int,
        name: str,
        description: str | None,
        origin: str,
    ) -> DatasetModel:
        dataset_name = name.strip()
        if not dataset_name:
            raise ValueError("O nome do dataset não pode ficar vazio")
        if not origin.strip():
            raise ValueError("A origem do dataset não pode ficar vazia")

        self.storage_path.mkdir(parents=True, exist_ok=True)
        partial_path = self.storage_path / f"upload_{uuid4().hex}.partial"
        artifact_path: Path | None = None
        total_started = perf_counter()
        try:
            upload_started = perf_counter()
            file_hash, file_size = stream_upload_to_file(
                stream, partial_path, self.max_upload_bytes, self.chunk_bytes
            )
            upload_seconds = perf_counter() - upload_started
            if self.repository.get_by_hash(file_hash) is not None:
                raise FileExistsError("Este arquivo já foi importado")

            artifact_path = self.storage_path / f"{file_hash}_{uuid4().hex}.csv"
            partial_path.replace(artifact_path)

            header_started = perf_counter()
            parser = DatasetCsvReader(artifact_path)
            header_seconds = perf_counter() - header_started

            dataset = DatasetModel(
                id_usuario=owner_id,
                nome=dataset_name,
                descricao=description,
                caminho_arquivo=str(artifact_path.resolve()),
                hash_arquivo=file_hash,
                total_registros=0,
                total_colunas=len(parser.colunas),
                origem=origin.strip(),
                possui_rotulo=parser.possui_rotulo,
            )
            dataset, stats = self.repository.create_with_copy(
                dataset,
                parser,
                copy_buffer_bytes=self.copy_buffer_bytes,
                progress_every_rows=self.progress_every_rows,
                on_progress=_log_progress,
            )
            total_seconds = perf_counter() - total_started
            rows_per_second = stats.rows_inserted / total_seconds if total_seconds else 0.0
            megabytes_per_second = (file_size / (1024 * 1024)) / total_seconds if total_seconds else 0.0
            logger.info(
                "Dataset %s importado arquivo=%s tamanho_bytes=%s linhas_processadas=%s "
                "linhas_invalidas=0 linhas_inseridas=%s tempo_upload=%.3fs tempo_cabecalho=%.3fs "
                "tempo_parsing=%.3fs tempo_copy=%.3fs tempo_commit=%.3fs tempo_total=%.3fs "
                "linhas_por_s=%.0f mb_por_s=%.2f",
                dataset.id_dataset,
                filename,
                file_size,
                stats.rows_inserted,
                stats.rows_inserted,
                upload_seconds,
                header_seconds,
                stats.parse_seconds,
                stats.copy_seconds,
                stats.commit_seconds,
                total_seconds,
                rows_per_second,
                megabytes_per_second,
            )
            return dataset
        except Exception:
            if partial_path.exists():
                partial_path.unlink(missing_ok=True)
            if artifact_path is not None and artifact_path.exists():
                artifact_path.unlink(missing_ok=True)
            raise


def _log_progress(dataset_id: int, rows: int) -> None:
    formatted = f"{rows:,}".replace(",", ".")
    logger.info("Processando dataset %s: %s linhas", dataset_id, formatted)


class GerenciarDatasetsUseCase:
    def __init__(self, repository: RepositorioDataset, storage_path: Path):
        self.repository = repository
        self.storage_path = storage_path.resolve()

    def list_datasets(self, owner_id: int, offset: int, limit: int) -> list[DatasetModel]:
        return self.repository.list_by_owner(owner_id, offset, limit)

    def get(self, dataset_id: int, owner_id: int) -> tuple[DatasetModel, list[TransacaoModel]]:
        dataset = self.repository.get_by_id(dataset_id, owner_id)
        if dataset is None:
            raise LookupError("Dataset não encontrado")
        return dataset, self.repository.get_sample_transactions(dataset.id_dataset)

    def delete(self, dataset_id: int, owner_id: int) -> None:
        started = perf_counter()
        artifact_location = self.repository.delete_owned(dataset_id, owner_id)
        if artifact_location is None:
            raise LookupError("Dataset não encontrado")
        artifact_path = Path(artifact_location).resolve()
        if artifact_path.is_relative_to(self.storage_path):
            artifact_path.unlink(missing_ok=True)
        logger.info(
            "Dataset %s excluído arquivo=%s tempo_total=%.3fs",
            dataset_id,
            artifact_path.name,
            perf_counter() - started,
        )
