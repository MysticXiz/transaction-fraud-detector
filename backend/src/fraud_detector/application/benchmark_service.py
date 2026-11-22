from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
import logging

from sqlalchemy.orm import Session

from src.fraud_detector.api.schemas.benchmark import BenchmarkConfiguracaoSchema
from src.fraud_detector.application.analysis_service import (
    create_execution,
    run_execution,
)
from src.fraud_detector.domain.enums.benchmark_role import PapelBenchmark
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.models.benchmark import (
    BenchmarkExecucaoModel,
    BenchmarkModel,
)
from src.fraud_detector.infrastructure.models.execution import MetricaExecucaoModel

logger = logging.getLogger(__name__)


def run_benchmark(db: Session, benchmark_id: int) -> None:
    try:
        benchmark = (
            db.query(BenchmarkModel)
            .filter_by(id_benchmark=benchmark_id)
            .with_for_update()
            .first()
        )
        if benchmark is None or benchmark.status != "PENDENTE":
            db.rollback()
            return
        config_payload = benchmark.configuracao
        if config_payload is None:
            raise ValueError("Configuração do benchmark não encontrada")
        owner_id = benchmark.id_usuario
        dataset_id = benchmark.id_dataset
        model_id = config_payload["id_modelo"]
        configs = config_payload["configuracoes"]
        benchmark.configuracao = {**config_payload, "inferencia_sincronizada": True}
        benchmark.status = "EM_ANDAMENTO"
        db.commit()

        baseline_seconds: Decimal | None = None
        configurations = [
            BenchmarkConfiguracaoSchema.model_validate(item) for item in configs
        ]
        ordered_configs = [
            item
            for item in configurations
            if item.modo_execucao == ModoExecucao.SEQUENCIAL
        ]
        ordered_configs.extend(
            item
            for item in configurations
            if item.modo_execucao == ModoExecucao.PARALELO
        )
        for config in ordered_configs:
            db.refresh(benchmark, with_for_update=True)
            if benchmark.status == "CANCELAMENTO_SOLICITADO":
                benchmark.status = "CANCELADO"
                db.commit()
                return

            execution = create_execution(
                db,
                owner_id=owner_id,
                dataset_id=dataset_id,
                model_id=model_id,
                mode=config.modo_execucao,
                work_group_size=config.work_group_size,
                device_type=(
                    config.tipo_dispositivo
                    if config.modo_execucao == ModoExecucao.PARALELO
                    else None
                ),
                chunk_size=None,
                threshold=None,
                commit=False,
            )
            role = (
                PapelBenchmark.BASELINE
                if config.modo_execucao == ModoExecucao.SEQUENCIAL
                else PapelBenchmark.COMPARACAO
            )
            association = BenchmarkExecucaoModel(
                id_benchmark=benchmark_id,
                id_execucao=execution.id_execucao,
                papel=role,
                tipo_dispositivo=config.tipo_dispositivo,
            )
            db.add(association)
            db.commit()

            db.refresh(benchmark, with_for_update=True)
            if benchmark.status in ("CANCELAMENTO_SOLICITADO", "CANCELADO"):
                execution.status = StatusExecucao.CANCELADA
                execution.finalizada_em = datetime.now(UTC)
                benchmark.status = "CANCELADO"
                db.commit()
                return
            db.commit()

            run_execution(
                db,
                execution.id_execucao,
                for_benchmark=True,
                opencl_device_type=(
                    config.tipo_dispositivo
                    if config.modo_execucao == ModoExecucao.PARALELO
                    else None
                ),
            )
            db.refresh(execution)
            db.refresh(benchmark)
            if (
                benchmark.status == "CANCELAMENTO_SOLICITADO"
                or execution.status == StatusExecucao.CANCELADA
            ):
                benchmark.status = "CANCELADO"
                db.commit()
                return
            if execution.status == StatusExecucao.FALHA:
                benchmark.status = "FALHA"
                benchmark.mensagem_erro = (
                    execution.mensagem_erro or "Uma configuração do benchmark falhou."
                )
                db.commit()
                return

            metric = (
                db.query(MetricaExecucaoModel)
                .filter_by(id_execucao=execution.id_execucao)
                .first()
            )
            elapsed = metric.tempo_inferencia_s if metric is not None else None
            if (
                role == PapelBenchmark.BASELINE
                and execution.status == StatusExecucao.CONCLUIDA
                and elapsed is not None
                and elapsed > 0
            ):
                baseline_seconds = elapsed
                association.speedup = Decimal("1")
                association.eficiencia = None
            elif (
                execution.status == StatusExecucao.CONCLUIDA
                and elapsed is not None
                and elapsed > 0
                and baseline_seconds is not None
                and baseline_seconds > 0
            ):
                speedup = _positive_decimal(
                    baseline_seconds / elapsed,
                    scale=4,
                    maximum=Decimal("9999.9999"),
                )
                association.speedup = speedup
                association.eficiencia = None
            db.commit()

        db.refresh(benchmark, with_for_update=True)
        benchmark.status = (
            "CANCELADO"
            if benchmark.status == "CANCELAMENTO_SOLICITADO"
            else "CONCLUIDO"
        )
        db.commit()
    except Exception as error:
        db.rollback()
        logger.exception("Falha ao executar benchmark %s", benchmark_id)
        benchmark = (
            db.query(BenchmarkModel).filter_by(id_benchmark=benchmark_id).first()
        )
        if benchmark is not None:
            if benchmark.status == "CANCELAMENTO_SOLICITADO":
                benchmark.status = "CANCELADO"
            else:
                benchmark.status = "FALHA"
                benchmark.mensagem_erro = str(error)[:2000]
            db.commit()


def _positive_decimal(
    value: Decimal, *, scale: int, maximum: Decimal
) -> Decimal | None:
    rounded = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
    return rounded if 0 < rounded <= maximum else None
