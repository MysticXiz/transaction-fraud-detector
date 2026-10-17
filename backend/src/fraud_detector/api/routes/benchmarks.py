from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
import logging
from xml.sax.saxutils import escape

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.dependencies.roles import require_write_access
from src.fraud_detector.api.schemas.benchmark import (
    BenchmarkConfiguracaoSchema,
    BenchmarkExecucaoRespostaSchema,
    BenchmarkRespostaSchema,
    CriarBenchmarkSchema,
)
from src.fraud_detector.api.schemas.opencl import OpenCLCapabilitiesSchema
from src.fraud_detector.application.analysis_service import (
    create_execution,
    run_execution,
)
from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLExecutionError,
    OpenCLIsolationForestExecutor,
    OpenCLRuntimeUnavailableError,
)
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.benchmark_role import PapelBenchmark
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.database.database import SessionLocal
from src.fraud_detector.infrastructure.models.benchmark import (
    BenchmarkExecucaoModel,
    BenchmarkModel,
)
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.detection_model import (
    ModeloDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.execution import ExecucaoAnaliseModel
from src.fraud_detector.infrastructure.models.user import UsuarioModel

benchmarks_router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])
logger = logging.getLogger(__name__)


@benchmarks_router.get(
    "/capacidades", response_model=OpenCLCapabilitiesSchema
)
def get_benchmark_capabilities(
    _: UsuarioModel = Depends(get_current_user),
):
    try:
        devices = OpenCLIsolationForestExecutor.available_devices()
    except (OpenCLExecutionError, OpenCLRuntimeUnavailableError) as error:
        raise HTTPException(
            status_code=503, detail=f"Dispositivo OpenCL indisponível: {error}"
        ) from error
    return OpenCLCapabilitiesSchema(
        dispositivos=[
            {
                "tipo": device_type,
                "plataforma": platform,
                "nome": device_name,
                "max_workers": max_workers,
            }
            for device_type, platform, device_name, max_workers in devices
        ]
    )


@benchmarks_router.post("", response_model=BenchmarkRespostaSchema)
def create_benchmark(
    payload: CriarBenchmarkSchema,
    background_tasks: BackgroundTasks,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    configs = payload.configuracoes
    baseline_configs = [
        item for item in configs if item.modo_execucao == ModoExecucao.SEQUENCIAL
    ]
    if (
        len(baseline_configs) != 1
        or baseline_configs[0].num_workers != 1
        or any(
            item.modo_execucao != ModoExecucao.PARALELO
            for item in configs
            if item is not baseline_configs[0]
        )
    ):
        raise HTTPException(
            status_code=422,
            detail="O benchmark deve conter uma configuração sequencial (1 worker), podendo incluir configurações paralelas adicionais",
        )

    dataset = (
        db.query(DatasetModel)
        .filter_by(
            id_dataset=payload.id_dataset,
            id_usuario=current_user.id_usuario,
        )
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset não encontrado")
    if dataset.total_registros < 2:
        raise HTTPException(
            status_code=422,
            detail="A detecção Isolation Forest exige ao menos duas transações",
        )
    model = db.query(ModeloDeteccaoModel).filter_by(id_modelo=payload.id_modelo).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Modelo de detecção não encontrado")
    if model.algoritmo != TipoAlgoritmo.ISOLATION_FOREST:
        raise HTTPException(
            status_code=422,
            detail="Benchmarks estão disponíveis apenas para Isolation Forest",
        )

    parallel_configs = [
        item for item in configs if item.modo_execucao == ModoExecucao.PARALELO
    ]
    for config in parallel_configs:
        if config.tipo_dispositivo is None:
            raise HTTPException(
                status_code=422,
                detail="Selecione CPU ou GPU para a configuração paralela",
            )
    if parallel_configs:
        try:
            devices = OpenCLIsolationForestExecutor.available_devices()
        except (OpenCLExecutionError, OpenCLRuntimeUnavailableError) as error:
            raise HTTPException(
                status_code=503, detail=f"Dispositivo OpenCL indisponível: {error}"
            ) from error
        device_limits = {device[0]: device[3] for device in devices}
        for config in parallel_configs:
            device_type = config.tipo_dispositivo
            if device_type is None:
                raise HTTPException(
                    status_code=422,
                    detail="Selecione CPU ou GPU para a configuração paralela",
                )
            max_workers = device_limits.get(device_type)
            if max_workers is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Não há dispositivo {device_type} OpenCL disponível",
                )
            if config.num_workers > max_workers:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"A quantidade de workers excede o limite ({max_workers}) "
                        f"do dispositivo {device_type} OpenCL"
                    ),
                )

    labels = ", ".join(item.rotulo for item in configs)
    description = (
        "Comparação OpenCL; num_workers define o tamanho do work-group, "
        "não o número de processos CPU. Configurações: " + labels
    )[:255]
    benchmark = BenchmarkModel(
        id_usuario=current_user.id_usuario,
        id_dataset=dataset.id_dataset,
        descricao=description,
        status="PENDENTE",
    )
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)

    background_tasks.add_task(
        run_benchmark_in_background,
        benchmark.id_benchmark,
        current_user.id_usuario,
        dataset.id_dataset,
        model.id_modelo,
        [item.model_dump() for item in configs],
    )
    return _benchmark_response(db, benchmark)


def run_benchmark_in_background(
    benchmark_id: int,
    owner_id: int,
    dataset_id: int,
    model_id: int,
    configs: list[dict[str, object]],
) -> None:
    db = SessionLocal()
    try:
        benchmark = db.query(BenchmarkModel).filter_by(id_benchmark=benchmark_id).first()
        if benchmark is None:
            return
        db.query(BenchmarkModel).filter(
            BenchmarkModel.id_benchmark == benchmark_id,
            BenchmarkModel.status == "PENDENTE",
        ).update({"status": "EM_ANDAMENTO"})
        db.commit()
        db.refresh(benchmark)
        if benchmark.status in ("CANCELADO", "CANCELAMENTO_SOLICITADO"):
            benchmark.status = "CANCELADO"
            db.commit()
            return

        baseline_seconds: Decimal | None = None
        configurations = [BenchmarkConfiguracaoSchema.model_validate(item) for item in configs]
        ordered_configs = [item for item in configurations if item.modo_execucao == ModoExecucao.SEQUENCIAL]
        ordered_configs.extend(
            item for item in configurations if item.modo_execucao == ModoExecucao.PARALELO
        )

        for config in ordered_configs:
            db.refresh(benchmark)
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
                workers=config.num_workers,
                device_type=(
                    config.tipo_dispositivo
                    if config.modo_execucao == ModoExecucao.PARALELO
                    else None
                ),
                chunk_size=None,
                threshold=None,
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

            db.refresh(benchmark)
            if benchmark.status in ("CANCELAMENTO_SOLICITADO", "CANCELADO"):
                execution.status = StatusExecucao.CANCELADA
                execution.finalizada_em = datetime.now(UTC)
                benchmark.status = "CANCELADO"
                db.commit()
                return

            run_execution(
                db,
                execution.id_execucao,
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
                benchmark.mensagem_erro = execution.mensagem_erro or "Uma configuração do benchmark falhou."
                db.commit()
                return

            elapsed = execution.tempo_total_s
            if role == PapelBenchmark.BASELINE and execution.status == StatusExecucao.CONCLUIDA:
                baseline_seconds = elapsed
                association.speedup = Decimal("1")
                association.eficiencia = Decimal("1")
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
                association.eficiencia = (
                    _positive_decimal(
                        speedup / Decimal(config.num_workers),
                        scale=4,
                        maximum=Decimal("99.9999"),
                    )
                    if speedup is not None
                    else None
                )
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
        benchmark = db.query(BenchmarkModel).filter_by(id_benchmark=benchmark_id).first()
        if benchmark is not None:
            if benchmark.status == "CANCELAMENTO_SOLICITADO":
                benchmark.status = "CANCELADO"
            else:
                benchmark.status = "FALHA"
                benchmark.mensagem_erro = str(error)[:2000]
            db.commit()
    finally:
        db.close()


@benchmarks_router.get("/{benchmark_id}", response_model=BenchmarkRespostaSchema)
def get_benchmark(
    benchmark_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark = _owned_benchmark(db, benchmark_id, current_user.id_usuario)
    return _benchmark_response(db, benchmark)


@benchmarks_router.post("/{benchmark_id}/cancelar", response_model=BenchmarkRespostaSchema)
def cancel_benchmark(
    benchmark_id: int,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    benchmark = _owned_benchmark(
        db, benchmark_id, current_user.id_usuario, for_update=True
    )
    if benchmark.status in ("CONCLUIDO", "FALHA", "CANCELADO"):
        raise HTTPException(status_code=409, detail="O benchmark já foi finalizado")
    if benchmark.status == "PENDENTE":
        benchmark.status = "CANCELADO"
    else:
        benchmark.status = "CANCELAMENTO_SOLICITADO"
        active_executions = (
            db.query(ExecucaoAnaliseModel)
            .join(
                BenchmarkExecucaoModel,
                BenchmarkExecucaoModel.id_execucao == ExecucaoAnaliseModel.id_execucao,
            )
            .filter(
                BenchmarkExecucaoModel.id_benchmark == benchmark_id,
                ExecucaoAnaliseModel.status.in_(
                    [StatusExecucao.PENDENTE, StatusExecucao.EM_ANDAMENTO]
                ),
            )
            .all()
        )
        for execution in active_executions:
            execution.status = StatusExecucao.CANCELADA
            execution.finalizada_em = datetime.now(UTC)
    db.commit()
    db.refresh(benchmark)
    return _benchmark_response(db, benchmark)


@benchmarks_router.get("/{benchmark_id}/exportar")
def export_benchmark_pdf(
    benchmark_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark = _owned_benchmark(db, benchmark_id, current_user.id_usuario)
    response = _benchmark_response(db, benchmark)
    return Response(
        _render_benchmark_pdf(response),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="benchmark-{benchmark_id}.pdf"'
        },
    )


def _render_benchmark_pdf(response: BenchmarkRespostaSchema) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    content = [
        Paragraph(f"Benchmark #{response.id_benchmark}", styles["Title"]),
        Paragraph(f"Dataset: {escape(response.dataset_nome)}", styles["Normal"]),
        Paragraph(f"Registros: {response.total_registros}", styles["Normal"]),
        Paragraph(f"Status: {response.status}", styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph(
            "Em modo OpenCL, num_workers representa o tamanho do work-group. "
            "Speedup e eficiência são medidas observadas, sem garantia de ganho.",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
    ]
    table_data = [
        [
            "Papel",
            "Modo",
            "Work-group",
            "Tempo (s)",
            "Speedup",
            "Eficiência",
            "Execução",
        ]
    ]
    table_data.extend(
        [
            item.papel.value,
            item.modo_execucao.value,
            str(item.num_workers),
            f"{item.tempo_s:.6f}" if item.tempo_s is not None else "N/D",
            f"{item.speedup:.4f}" if item.speedup is not None else "N/D",
            f"{item.eficiencia:.4f}" if item.eficiencia is not None else "N/D",
            str(item.id_execucao),
        ]
        for item in response.execucoes
    )
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#40306b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cccccc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f2eff8")],
                ),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    content.append(table)
    document.build(content)
    return buffer.getvalue()


def _owned_benchmark(
    db: Session, benchmark_id: int, owner_id: int, *, for_update: bool = False
):
    query = (
        db.query(BenchmarkModel)
        .filter(
            BenchmarkModel.id_benchmark == benchmark_id,
            BenchmarkModel.id_usuario == owner_id,
        )
    )
    if for_update:
        query = query.with_for_update()
    benchmark = query.first()
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Benchmark não encontrado")
    return benchmark


def _benchmark_response(
    db: Session, benchmark: BenchmarkModel
) -> BenchmarkRespostaSchema:
    dataset = db.query(DatasetModel).filter_by(id_dataset=benchmark.id_dataset).first()
    rows = (
        db.query(BenchmarkExecucaoModel, ExecucaoAnaliseModel)
        .join(
            ExecucaoAnaliseModel,
            ExecucaoAnaliseModel.id_execucao == BenchmarkExecucaoModel.id_execucao,
        )
        .filter(BenchmarkExecucaoModel.id_benchmark == benchmark.id_benchmark)
        .order_by(BenchmarkExecucaoModel.id_benchmark_exec)
        .all()
    )
    items = [
        BenchmarkExecucaoRespostaSchema(
            id_benchmark_exec=association.id_benchmark_exec,
            id_execucao=execution.id_execucao,
            papel=association.papel,
            tipo_dispositivo=association.tipo_dispositivo,
            modo_execucao=execution.modo_execucao,
            num_workers=execution.num_workers,
            tempo_s=execution.tempo_total_s,
            speedup=association.speedup,
            eficiencia=association.eficiencia,
        )
        for association, execution in rows
    ]
    return BenchmarkRespostaSchema(
        id_benchmark=benchmark.id_benchmark,
        id_dataset=benchmark.id_dataset,
        dataset_nome=dataset.nome if dataset else "Dataset removido",
        total_registros=dataset.total_registros if dataset else 0,
        descricao=benchmark.descricao,
        criado_em=benchmark.criado_em,
        status=benchmark.status,
        mensagem_erro=benchmark.mensagem_erro,
        execucoes=items,
    )


def _positive_decimal(
    value: Decimal, *, scale: int, maximum: Decimal
) -> Decimal | None:
    rounded = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
    return rounded if 0 < rounded <= maximum else None
