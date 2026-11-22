from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.dependencies.roles import require_write_access
from src.fraud_detector.api.schemas.benchmark import (
    BenchmarkExecucaoRespostaSchema,
    BenchmarkRespostaSchema,
    CriarBenchmarkSchema,
)
from src.fraud_detector.api.schemas.opencl import (
    OpenCLCapabilitiesSchema,
    OpenCLDeviceSchema,
)
from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLExecutionError,
    OpenCLIsolationForestExecutor,
    OpenCLRuntimeUnavailableError,
)
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.models.benchmark import (
    BenchmarkExecucaoModel,
    BenchmarkModel,
)
from src.fraud_detector.infrastructure.models.execution import MetricaExecucaoModel
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.detection_model import (
    ModeloDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.execution import ExecucaoAnaliseModel
from src.fraud_detector.infrastructure.models.user import UsuarioModel

benchmarks_router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])


def _benchmark_device_capability(
    device_type: str,
    platform: str,
    device_name: str,
    max_work_group_size: int,
) -> OpenCLDeviceSchema:
    recommendation = OpenCLIsolationForestExecutor.recommend_for_device(
        device_type="GPU" if device_type == "GPU" else "CPU",
    )
    return OpenCLDeviceSchema(
        tipo=device_type,
        plataforma=platform,
        nome=device_name,
        max_work_group_size=max_work_group_size,
        work_group_recomendado=int(recommendation["work_group_recomendado"]),
        chunk_recomendado=int(recommendation["chunk_recomendado"]),
        preferred_work_group_multiple=int(
            recommendation["preferred_work_group_multiple"]
        ),
        unidades_computacao=int(recommendation["max_compute_units"]),
        local_mem_size=int(recommendation["local_mem_size"]),
    )


@benchmarks_router.get("/capacidades", response_model=OpenCLCapabilitiesSchema)
def get_benchmark_capabilities(
    _: UsuarioModel = Depends(get_current_user),
):
    try:
        devices = OpenCLIsolationForestExecutor.available_devices()
    except (OpenCLExecutionError, OpenCLRuntimeUnavailableError):
        return OpenCLCapabilitiesSchema(dispositivos=[])
    return OpenCLCapabilitiesSchema(
        dispositivos=[
            _benchmark_device_capability(
                device_type,
                platform,
                device_name,
                max_work_group_size,
            )
            for device_type, platform, device_name, max_work_group_size in devices
        ]
    )


@benchmarks_router.post("", response_model=BenchmarkRespostaSchema, status_code=202)
def create_benchmark(
    payload: CriarBenchmarkSchema,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    configs = payload.configuracoes
    for config in configs:
        if (
            config.modo_execucao == ModoExecucao.SEQUENCIAL
            and config.work_group_size is None
        ):
            config.work_group_size = 1
    baseline_configs = [
        item for item in configs if item.modo_execucao == ModoExecucao.SEQUENCIAL
    ]
    parallel_configs = [
        item for item in configs if item.modo_execucao == ModoExecucao.PARALELO
    ]
    if len(baseline_configs) > 1:
        raise HTTPException(
            status_code=422,
            detail="O benchmark pode conter apenas uma configuração sequencial (baseline)",
        )
    if baseline_configs and baseline_configs[0].work_group_size != 1:
        raise HTTPException(
            status_code=422,
            detail="O baseline sequencial deve usar work-group igual a 1",
        )
    if not baseline_configs and not parallel_configs:
        raise HTTPException(
            status_code=422,
            detail="O benchmark deve conter ao menos uma configuração de execução",
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
            max_work_group_size = device_limits.get(device_type)
            if max_work_group_size is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Não há dispositivo {device_type} OpenCL disponível",
                )
            if config.work_group_size is None:
                recommendation = OpenCLIsolationForestExecutor.recommend_for_device(
                    device_type,
                    dataset_size=dataset.total_registros or 50_000,
                )
                config.work_group_size = int(recommendation["work_group_recomendado"])
            if config.work_group_size > max_work_group_size:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"O tamanho do work-group excede o limite ({max_work_group_size}) "
                        f"do dispositivo {device_type} OpenCL"
                    ),
                )

    labels = ", ".join(item.rotulo for item in configs)
    description = (
        "Comparação OpenCL; work_group_size define o tamanho do work-group, "
        "não o número de processos CPU. Configurações: " + labels
    )[:255]
    benchmark = BenchmarkModel(
        id_usuario=current_user.id_usuario,
        id_dataset=dataset.id_dataset,
        descricao=description,
        status="PENDENTE",
        configuracao={
            "id_modelo": model.id_modelo,
            "configuracoes": [item.model_dump(mode="json") for item in configs],
        },
    )
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)

    return _benchmark_response(db, benchmark)


@benchmarks_router.get("/{benchmark_id}", response_model=BenchmarkRespostaSchema)
def get_benchmark(
    benchmark_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark = _owned_benchmark(db, benchmark_id, current_user.id_usuario)
    return _benchmark_response(db, benchmark)


@benchmarks_router.post(
    "/{benchmark_id}/cancelar", response_model=BenchmarkRespostaSchema
)
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


def _owned_benchmark(
    db: Session, benchmark_id: int, owner_id: int, *, for_update: bool = False
):
    query = db.query(BenchmarkModel).filter(
        BenchmarkModel.id_benchmark == benchmark_id,
        BenchmarkModel.id_usuario == owner_id,
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
    items = []
    for association, execution in rows:
        metric = (
            db.query(MetricaExecucaoModel)
            .filter_by(id_execucao=execution.id_execucao)
            .first()
        )
        items.append(
            BenchmarkExecucaoRespostaSchema(
                id_benchmark_exec=association.id_benchmark_exec,
                id_execucao=execution.id_execucao,
                papel=association.papel,
                tipo_dispositivo=association.tipo_dispositivo,
                modo_execucao=execution.modo_execucao,
                work_group_size=execution.num_workers,
                tempo_s=execution.tempo_total_s,
                tempo_inferencia_s=(
                    metric.tempo_inferencia_s if metric is not None else None
                ),
                speedup=association.speedup,
                eficiencia=association.eficiencia,
            )
        )
    return BenchmarkRespostaSchema(
        id_benchmark=benchmark.id_benchmark,
        id_dataset=benchmark.id_dataset,
        dataset_nome=dataset.nome if dataset else "Dataset removido",
        total_registros=dataset.total_registros if dataset else 0,
        descricao=benchmark.descricao,
        criado_em=benchmark.criado_em,
        status=benchmark.status,
        mensagem_erro=benchmark.mensagem_erro,
        inferencia_sincronizada=(benchmark.configuracao or {}).get(
            "inferencia_sincronizada", False
        ),
        execucoes=items,
    )
