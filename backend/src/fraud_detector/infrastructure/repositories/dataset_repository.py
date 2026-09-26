from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.fraud_detector.computational.ingestion.dataset_csv import DatasetCsvReader
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel


COPY_STATEMENT = (
    "COPY transacao "
    "(id_dataset, indice_origem, valor, tempo_relativo, atributos, rotulo_real) "
    "FROM STDIN"
)


@dataclass(slots=True)
class IngestionLoadStats:
    rows_inserted: int
    parse_seconds: float
    copy_seconds: float
    copy_finalize_seconds: float
    commit_seconds: float


def _driver_connection(session: Session):
    sa_connection = session.connection()
    raw = sa_connection.connection

    return (
        getattr(raw, "driver_connection", None)
        or getattr(raw, "dbapi_connection", None)
        or raw
    )


class RepositorioDataset:

    def __init__(self, db: Session):
        self.db = db

    def get_by_hash(self, file_hash: str) -> DatasetModel | None:
        return (
            self.db.query(DatasetModel)
            .filter(DatasetModel.hash_arquivo == file_hash)
            .first()
        )

    def create_with_copy(
        self,
        dataset: DatasetModel,
        parser: DatasetCsvReader,
        *,
        copy_buffer_bytes: int = 1_048_576,
        progress_every_rows: int = 50_000,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[DatasetModel, IngestionLoadStats]:

        parse_seconds = 0.0
        copy_seconds = 0.0
        copy_finalize_seconds = 0.0

        try:
            self.db.add(dataset)
            self.db.flush()

            total_records = 0
            driver = _driver_connection(self.db)

            with driver.cursor() as cursor:

                copy_started = perf_counter()

                with cursor.copy(COPY_STATEMENT) as copy:

                    buffer = bytearray()

                    parse_started = perf_counter()

                    for line in parser.iter_copy_text(dataset.id_dataset):

                        parse_seconds += perf_counter() - parse_started

                        if total_records + 1 > 2_147_483_647:
                            raise ValueError(
                                "O arquivo excede a quantidade máxima de transações"
                            )

                        write_started = perf_counter()

                        buffer.extend(line)
                        total_records += 1

                        if len(buffer) >= copy_buffer_bytes:
                            copy.write(bytes(buffer))
                            buffer.clear()

                        copy_seconds += perf_counter() - write_started

                        if (
                            on_progress
                            and total_records % progress_every_rows == 0
                        ):
                            on_progress(
                                dataset.id_dataset,
                                total_records,
                            )

                        parse_started = perf_counter()

                    parse_seconds += perf_counter() - parse_started

                    if buffer:
                        write_started = perf_counter()

                        copy.write(bytes(buffer))

                        copy_seconds += perf_counter() - write_started

                    # Tudo que estava dentro do COPY terminou.
                    # O próximo passo é sair do `with`, que finaliza o COPY.
                    copy_body_finished = perf_counter()

                # Mede exclusivamente a finalização do COPY.
                copy_finalize_seconds = (
                    perf_counter() - copy_body_finished
                )

            if total_records == 0:
                raise ValueError(
                    "O arquivo CSV precisa conter ao menos uma transação"
                )

            dataset.total_registros = total_records

            commit_started = perf_counter()

            self.db.commit()

            commit_seconds = perf_counter() - commit_started

            self.db.refresh(dataset)

            return dataset, IngestionLoadStats(
                rows_inserted=total_records,
                parse_seconds=parse_seconds,
                copy_seconds=copy_seconds,
                copy_finalize_seconds=copy_finalize_seconds,
                commit_seconds=commit_seconds,
            )

        except Exception:
            self.db.rollback()
            raise

    def list_by_owner(
        self,
        owner_id: int,
        offset: int,
        limit: int,
    ) -> list[DatasetModel]:

        return (
            self.db.query(DatasetModel)
            .filter(DatasetModel.id_usuario == owner_id)
            .order_by(
                DatasetModel.importado_em.desc(),
                DatasetModel.id_dataset.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_id(
        self,
        dataset_id: int,
        owner_id: int,
    ) -> DatasetModel | None:

        return (
            self.db.query(DatasetModel)
            .filter(
                DatasetModel.id_dataset == dataset_id,
                DatasetModel.id_usuario == owner_id,
            )
            .first()
        )

    def get_sample_transactions(
        self,
        dataset_id: int,
        limit: int = 10,
    ) -> list[TransacaoModel]:

        return (
            self.db.query(TransacaoModel)
            .filter(TransacaoModel.id_dataset == dataset_id)
            .order_by(TransacaoModel.indice_origem)
            .limit(limit)
            .all()
        )

    def delete_owned(
        self,
        dataset_id: int,
        owner_id: int,
    ) -> str | None:

        try:
            result = self.db.execute(
                text(
                    "DELETE FROM dataset "
                    "WHERE id_dataset = :dataset_id "
                    "AND id_usuario = :owner_id "
                    "RETURNING caminho_arquivo"
                ),
                {
                    "dataset_id": dataset_id,
                    "owner_id": owner_id,
                },
            )

            row = result.first()

            if row is None:
                return None

            self.db.commit()

            return row[0]

        except IntegrityError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise