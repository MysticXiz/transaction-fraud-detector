"""Executa a fila de análises e benchmarks persistida no PostgreSQL."""

from datetime import UTC, datetime
import logging
from threading import Event

from sqlalchemy import exists, select, update

from src.fraud_detector.application.analysis_service import run_execution
from src.fraud_detector.application.benchmark_service import run_benchmark
from src.fraud_detector.application.execution_errors import EXECUTION_INTERRUPTED
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.compute_lock import try_compute_lock
from src.fraud_detector.infrastructure.database.database import SessionLocal
from src.fraud_detector.infrastructure.models.benchmark import (
    BenchmarkExecucaoModel,
    BenchmarkModel,
)
from src.fraud_detector.infrastructure.models.execution import ExecucaoAnaliseModel

logger = logging.getLogger(__name__)


def process_next_job() -> bool:
    with try_compute_lock() as acquired:
        if not acquired:
            return False

        with SessionLocal() as db:
            # O lock garante que nenhuma outra instância esteja executando estes jobs.
            db.execute(
                update(ExecucaoAnaliseModel)
                .where(ExecucaoAnaliseModel.status == StatusExecucao.EM_ANDAMENTO)
                .values(
                    status=StatusExecucao.FALHA,
                    mensagem_erro=EXECUTION_INTERRUPTED,
                    finalizada_em=datetime.now(UTC),
                )
            )
            db.execute(
                update(BenchmarkModel)
                .where(BenchmarkModel.status == "CANCELAMENTO_SOLICITADO")
                .values(status="CANCELADO")
            )
            db.execute(
                update(BenchmarkModel)
                .where(
                    (BenchmarkModel.status == "EM_ANDAMENTO")
                    | (
                        (BenchmarkModel.status == "PENDENTE")
                        & BenchmarkModel.configuracao.is_(None)
                    )
                )
                .values(status="FALHA", mensagem_erro=EXECUTION_INTERRUPTED)
            )
            db.execute(
                update(ExecucaoAnaliseModel)
                .where(
                    ExecucaoAnaliseModel.status == StatusExecucao.PENDENTE,
                    exists(
                        select(1)
                        .select_from(BenchmarkExecucaoModel)
                        .join(BenchmarkModel)
                        .where(
                            BenchmarkExecucaoModel.id_execucao
                            == ExecucaoAnaliseModel.id_execucao,
                            BenchmarkModel.status == "FALHA",
                        )
                    ),
                )
                .values(
                    status=StatusExecucao.FALHA,
                    mensagem_erro=EXECUTION_INTERRUPTED,
                    finalizada_em=datetime.now(UTC),
                )
            )

            analysis = db.execute(
                select(ExecucaoAnaliseModel.id_execucao, ExecucaoAnaliseModel.criado_em)
                .where(
                    ExecucaoAnaliseModel.status == StatusExecucao.PENDENTE,
                    ~exists().where(
                        BenchmarkExecucaoModel.id_execucao
                        == ExecucaoAnaliseModel.id_execucao
                    ),
                )
                .order_by(
                    ExecucaoAnaliseModel.criado_em, ExecucaoAnaliseModel.id_execucao
                )
                .limit(1)
            ).first()
            benchmark = db.execute(
                select(BenchmarkModel.id_benchmark, BenchmarkModel.criado_em)
                .where(BenchmarkModel.status == "PENDENTE")
                .order_by(BenchmarkModel.criado_em, BenchmarkModel.id_benchmark)
                .limit(1)
            ).first()
            db.commit()

            if benchmark is not None and (
                analysis is None or benchmark[1] < analysis[1]
            ):
                run_benchmark(db, benchmark[0])
            elif analysis is not None:
                run_execution(db, analysis[0])
            else:
                return False
        return True


def process_queue(stop: Event) -> None:
    while not stop.is_set():
        try:
            if process_next_job():
                continue
        except Exception:
            logger.exception("Falha no processamento da fila de análises e benchmarks")
        stop.wait(1)
