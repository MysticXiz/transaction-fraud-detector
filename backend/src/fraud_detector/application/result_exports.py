import csv
import io
import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Literal

from sqlalchemy import select

from src.fraud_detector.infrastructure.database.database import SessionLocal
from src.fraud_detector.infrastructure.models.execution import ResultadoDeteccaoModel
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel

ExportFormat = Literal["csv", "json"]
_RESULT = ResultadoDeteccaoModel
_TRANSACTION = TransacaoModel
_COLUMNS = (
    _RESULT.id_execucao,
    _RESULT.id_transacao,
    _TRANSACTION.indice_origem,
    _RESULT.score_anomalia,
    _RESULT.is_suspeita,
    _RESULT.limiar_aplicado,
    _RESULT.chunk_id,
    _TRANSACTION.valor,
    _TRANSACTION.tempo_relativo,
    _TRANSACTION.rotulo_real,
    _TRANSACTION.atributos,
)
_FIELD_NAMES = tuple(column.key for column in _COLUMNS)
_BATCH_ROWS = 500


def result_filters(
    execution_id: int,
    minimum_score: Decimal | None,
    minimum_amount: Decimal | None,
    suspicious: bool | None,
):
    conditions = [_RESULT.id_execucao == execution_id]
    if minimum_score is not None:
        conditions.append(_RESULT.score_anomalia >= minimum_score)
    if minimum_amount is not None:
        conditions.append(_TRANSACTION.valor >= minimum_amount)
    if suspicious is not None:
        conditions.append(_RESULT.is_suspeita.is_(suspicious))
    return conditions


def stream_results(
    execution_id: int,
    export_format: ExportFormat,
    minimum_score: Decimal | None,
    minimum_amount: Decimal | None,
    suspicious: bool | None,
) -> Iterator[str]:
    statement = (
        select(*_COLUMNS)
        .select_from(_RESULT)
        .join(_TRANSACTION, _TRANSACTION.id_transacao == _RESULT.id_transacao)
        .where(*result_filters(execution_id, minimum_score, minimum_amount, suspicious))
        .order_by(_RESULT.score_anomalia.desc(), _RESULT.id_transacao)
        .execution_options(yield_per=_BATCH_ROWS)
    )

    with SessionLocal() as db, db.execute(statement) as rows:
        if export_format == "csv":
            with io.StringIO(newline="") as output:
                writer = csv.writer(output)
                writer.writerow(_FIELD_NAMES)
                yield output.getvalue()
                for batch in rows.partitions(_BATCH_ROWS):
                    output.seek(0)
                    output.truncate()
                    writer.writerows(
                        (*row[:-1], json.dumps(row[-1], ensure_ascii=False))
                        for row in batch
                    )
                    yield output.getvalue()
        else:
            yield "["
            separator = "\n"
            for batch in rows.mappings().partitions(_BATCH_ROWS):
                yield separator + ",\n".join(
                    json.dumps(
                        dict(row),
                        ensure_ascii=False,
                        default=float,
                        separators=(",", ":"),
                    )
                    for row in batch
                )
                separator = ",\n"
            yield "\n]\n"
