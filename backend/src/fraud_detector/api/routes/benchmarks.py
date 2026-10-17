from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.schemas.benchmark import (
    BenchmarkExecucaoRespostaSchema,
    BenchmarkRespostaSchema,
    CriarBenchmarkSchema,
)
from src.fraud_detector.application.analysis_service import (
    AnalysisNotFoundError,
    AnalysisRequestError,
    create_execution,
    run_execution,
)
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.benchmark_role import PapelBenchmark
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import get_db
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


@benchmarks_router.post("", response_model=BenchmarkRespostaSchema)
def create_benchmark(
    payload: CriarBenchmarkSchema,
    current_user: UsuarioModel = Depends(get_current_user),
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
            detail="O benchmark deve conter uma configuração sequencial (1 worker) e apenas configurações paralelas adicionais",
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

    labels = ", ".join(item.rotulo for item in configs)
    description = (
        "Comparação OpenCL; num_workers define o tamanho do work-group, "
        "não o número de processos CPU. Configurações: " + labels
    )[:255]
    benchmark = BenchmarkModel(
        id_usuario=current_user.id_usuario,
        id_dataset=dataset.id_dataset,
        descricao=description,
    )
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)

    baseline_seconds: Decimal | None = None
    ordered_configs = baseline_configs + [
        item for item in configs if item.modo_execucao == ModoExecucao.PARALELO
    ]
    for config in ordered_configs:
        try:
            execution = create_execution(
                db,
                owner_id=current_user.id_usuario,
                dataset_id=dataset.id_dataset,
                model_id=model.id_modelo,
                mode=config.modo_execucao,
                workers=config.num_workers,
                chunk_size=None,
                threshold=None,
            )
        except AnalysisRequestError as error:
            if isinstance(error, AnalysisNotFoundError):
                raise HTTPException(status_code=404, detail=str(error)) from error
            raise HTTPException(status_code=422, detail=str(error)) from error
        run_execution(db, execution.id_execucao)
        db.refresh(execution)

        role = (
            PapelBenchmark.BASELINE
            if config.modo_execucao == ModoExecucao.SEQUENCIAL
            else PapelBenchmark.COMPARACAO
        )
        elapsed = execution.tempo_total_s
        if (
            role == PapelBenchmark.BASELINE
            and execution.status == StatusExecucao.CONCLUIDA
        ):
            baseline_seconds = elapsed
            speedup = Decimal("1")
            efficiency = Decimal("1")
        elif (
            execution.status == StatusExecucao.CONCLUIDA
            and elapsed is not None
            and elapsed > 0
            and baseline_seconds is not None
            and baseline_seconds > 0
        ):
            speedup = _positive_decimal(
                baseline_seconds / elapsed, scale=4, maximum=Decimal("9999.9999")
            )
            efficiency = (
                _positive_decimal(
                    speedup / Decimal(config.num_workers),
                    scale=4,
                    maximum=Decimal("99.9999"),
                )
                if speedup is not None
                else None
            )
        else:
            speedup = None
            efficiency = None
        db.add(
            BenchmarkExecucaoModel(
                id_benchmark=benchmark.id_benchmark,
                id_execucao=execution.id_execucao,
                papel=role,
                speedup=speedup,
                eficiencia=efficiency,
            )
        )
        db.commit()
    return _benchmark_response(db, benchmark)


@benchmarks_router.get("/{benchmark_id}", response_model=BenchmarkRespostaSchema)
def get_benchmark(
    benchmark_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark = _owned_benchmark(db, benchmark_id, current_user.id_usuario)
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


def _owned_benchmark(db: Session, benchmark_id: int, owner_id: int):
    benchmark = (
        db.query(BenchmarkModel)
        .filter(
            BenchmarkModel.id_benchmark == benchmark_id,
            BenchmarkModel.id_usuario == owner_id,
        )
        .first()
    )
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
    if any(
        execution.status in (StatusExecucao.FALHA, StatusExecucao.CANCELADA)
        for _, execution in rows
    ):
        benchmark_status = "FALHA"
    elif all(execution.status == StatusExecucao.CONCLUIDA for _, execution in rows):
        benchmark_status = "CONCLUIDO"
    else:
        benchmark_status = "EM_ANDAMENTO"
    items = [
        BenchmarkExecucaoRespostaSchema(
            id_benchmark_exec=association.id_benchmark_exec,
            id_execucao=execution.id_execucao,
            papel=association.papel,
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
        status=benchmark_status,
        execucoes=items,
    )


def _positive_decimal(
    value: Decimal, *, scale: int, maximum: Decimal
) -> Decimal | None:
    rounded = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
    return rounded if 0 < rounded <= maximum else None
