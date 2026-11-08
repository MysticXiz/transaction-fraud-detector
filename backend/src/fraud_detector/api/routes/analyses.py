import csv
import io
import json
import logging
import os
from xml.sax.saxutils import escape
from hashlib import sha256
from decimal import Decimal
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

import numpy as np
import psutil
import pyopencl as cl
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.dependencies.roles import require_write_access
from src.fraud_detector.api.schemas.analysis import (
    AvaliacaoHistoricoSchema,
    CriarExecucaoSchema,
    DetalheResultadoSchema,
    ExecucaoRespostaSchema,
    MetricaRespostaSchema,
    ModeloRespostaSchema,
    ResultadoAtualSchema,
    ResultadoRespostaSchema,
    ResultadosPaginaSchema,
    TransacaoDetalheSchema,
)
from src.fraud_detector.api.schemas.opencl import (
    CalibracaoCandidatoSchema,
    CalibracaoOpenCLRespostaSchema,
    CalibrarOpenCLSchema,
    OpenCLCapabilitiesSchema,
    OpenCLDeviceSchema,
)
from src.fraud_detector.application.analysis_service import (
    _ANALYSIS_LOCK,
    AnalysisNotFoundError,
    AnalysisRequestError,
    create_execution,
    run_execution_in_background,
)
from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLExecutionError,
    OpenCLIsolationForestExecutor,
    OpenCLRuntimeUnavailableError,
)
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import SessionLocal, get_db
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.detection_model import (
    ModeloDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.execution import (
    ExecucaoAnaliseModel,
    MetricaExecucaoModel,
    ResultadoDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.benchmark import (
    BenchmarkExecucaoModel,
    BenchmarkModel,
)
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel
from src.fraud_detector.infrastructure.models.user import UsuarioModel

analyses_router = APIRouter(prefix="/analises", tags=["Análises"])
models_router = APIRouter(prefix="/modelos", tags=["Modelos"])
logger = logging.getLogger(__name__)
_CALIBRATION_CACHE: dict[str, CalibracaoOpenCLRespostaSchema] = {}


def _device_capability(
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


@analyses_router.get("/capacidades", response_model=OpenCLCapabilitiesSchema)
def get_analysis_capabilities(
    _: UsuarioModel = Depends(get_current_user),
):
    try:
        devices = OpenCLIsolationForestExecutor.available_devices()
    except Exception as error:
        logger.info("Não foi possível enumerar dispositivos OpenCL: %s", error)
        return OpenCLCapabilitiesSchema(dispositivos=[])
    return OpenCLCapabilitiesSchema(
        dispositivos=[
            _device_capability(device_type, platform, device_name, max_work_group_size)
            for device_type, platform, device_name, max_work_group_size in devices
        ]
    )


@analyses_router.get("/diagnostico-opencl")
def diagnose_opencl(_: UsuarioModel = Depends(get_current_user)):
    platforms: list[dict[str, object]] = []
    try:
        for platform in cl.get_platforms():
            devices: list[str] = []
            for device in platform.get_devices():
                devices.append(device.name)
            platforms.append({"plataforma": platform.name, "dispositivos": devices})
    except Exception as error:
        logger.info("Falha ao diagnosticar OpenCL: %s", error)
    return {
        "plataformas": platforms,
        "cpus_disponiveis_processo": psutil.cpu_count(logical=True) or 1,
        "pocl_max_pu_count": os.getenv("POCL_MAX_PU_COUNT"),
        "omp_num_threads": os.getenv("OMP_NUM_THREADS"),
        "openblas_num_threads": os.getenv("OPENBLAS_NUM_THREADS"),
        "pocl_pthread": any(
            "Portable Computing Language" in str(platform["plataforma"])
            for platform in platforms
        ),
    }


@analyses_router.post(
    "/calibrar-opencl",
    response_model=CalibracaoOpenCLRespostaSchema,
)
def calibrate_opencl(
    payload: CalibrarOpenCLSchema,
    _: UsuarioModel = Depends(require_write_access),
):
    if not _ANALYSIS_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Existe uma análise em execução; aguarde a conclusão para calibrar o OpenCL",
        )
    try:
        try:
            devices = OpenCLIsolationForestExecutor.available_devices()
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Não foi possível detectar um dispositivo OpenCL disponível",
            ) from error
        if not any(device[0] == payload.tipo_dispositivo for device in devices):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Não há dispositivo {payload.tipo_dispositivo} OpenCL disponível",
            )

        recommendation = OpenCLIsolationForestExecutor.recommend_for_device(
            payload.tipo_dispositivo,
            dataset_size=payload.tamanho_amostra,
        )
        max_work_group = int(recommendation["max_work_group_size"])
        preferred = int(recommendation["preferred_work_group_multiple"])
        chunk_recommended = int(recommendation["chunk_recomendado"])
        cache_key = sha256(
            (
                f"{payload.tipo_dispositivo}:"
                f"{payload.tamanho_amostra}:{max_work_group}:{preferred}:{chunk_recommended}"
            ).encode("utf-8")
        ).hexdigest()
        cached = _CALIBRATION_CACHE.get(cache_key)
        if cached is not None:
            return cached

        rng = np.random.default_rng(42)
        samples = rng.normal(size=(payload.tamanho_amostra, 8)).astype(np.float32)
        executor = OpenCLIsolationForestExecutor(
            n_estimators=50,
            device_type=payload.tipo_dispositivo,
        )
        executor.fit(samples)

        candidates: list[CalibracaoCandidatoSchema] = []
        work_groups: list[int] = []
        candidate = preferred
        while candidate <= max_work_group:
            work_groups.append(candidate)
            candidate *= 2
        if max_work_group not in work_groups:
            work_groups.append(max_work_group)
        work_groups = sorted(set(max(1, candidate) for candidate in work_groups))

        started_all = perf_counter()
        best_candidate: CalibracaoCandidatoSchema | None = None
        for work_group in work_groups:
            elapsed = perf_counter() - started_all
            if elapsed >= payload.tempo_maximo_s:
                break
            started = perf_counter()
            try:
                executor.score_opencl(samples, work_group_size=work_group)
            except (
                OpenCLExecutionError,
                OpenCLRuntimeUnavailableError,
                ValueError,
            ) as error:
                logger.warning(
                    "Candidato de calibração work-group=%s falhou: %s",
                    work_group,
                    error,
                )
                continue
            duration = max(perf_counter() - started, 0.000001)
            candidate_result = CalibracaoCandidatoSchema(
                work_group_size=work_group,
                tamanho_chunk=chunk_recommended,
                throughput_tps=payload.tamanho_amostra / duration,
                tempo_s=duration,
            )
            candidates.append(candidate_result)
            if (
                best_candidate is None
                or candidate_result.throughput_tps > best_candidate.throughput_tps
            ):
                best_candidate = candidate_result

        if best_candidate is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nenhum candidato de work-group conseguiu executar neste dispositivo",
            )
        response = CalibracaoOpenCLRespostaSchema(
            tipo_dispositivo=payload.tipo_dispositivo,
            work_group_size_recomendado=best_candidate.work_group_size,
            tamanho_chunk_recomendado=chunk_recommended,
            candidatos=candidates,
            explicacao=(
                "A calibração mediu os candidatos em dados sintéticos. "
                "O work-group escolhido obteve o maior rendimento."
            ),
        )
        _CALIBRATION_CACHE[cache_key] = response
        return response
    finally:
        _ANALYSIS_LOCK.release()


@analyses_router.post(
    "",
    response_model=ExecucaoRespostaSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_analysis(
    payload: CriarExecucaoSchema,
    background_tasks: BackgroundTasks,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    if payload.modo_execucao == ModoExecucao.SEQUENCIAL:
        if payload.tipo_dispositivo is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A execução sequencial não seleciona dispositivo OpenCL",
            )
    elif payload.tipo_dispositivo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selecione CPU ou GPU para a execução paralela",
        )
    else:
        try:
            devices = OpenCLIsolationForestExecutor.available_devices()
        except (OpenCLExecutionError, OpenCLRuntimeUnavailableError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dispositivo OpenCL indisponível: {error}",
            ) from error
        selected_device = next(
            (device for device in devices if device[0] == payload.tipo_dispositivo),
            None,
        )
        if selected_device is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Não há dispositivo {payload.tipo_dispositivo} OpenCL disponível",
            )
        if (
            payload.work_group_size is not None
            and payload.work_group_size > selected_device[3]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"O tamanho do work-group excede o limite "
                    f"({selected_device[3]}) do dispositivo "
                    f"{payload.tipo_dispositivo} OpenCL"
                ),
            )

    try:
        execution = create_execution(
            db,
            owner_id=current_user.id_usuario,
            dataset_id=payload.id_dataset,
            model_id=payload.id_modelo,
            mode=payload.modo_execucao,
            work_group_size=payload.work_group_size,
            device_type=payload.tipo_dispositivo,
            chunk_size=payload.tamanho_chunk,
            threshold=payload.limiar_decisao,
        )
    except AnalysisRequestError as error:
        if isinstance(error, AnalysisNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
            ) from error
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    background_tasks.add_task(run_execution_in_background, execution.id_execucao)
    return _execution_response(db, execution)


@analyses_router.get("", response_model=list[ExecucaoRespostaSchema])
def list_analyses(
    status_filter: StatusExecucao | None = Query(default=None, alias="status"),
    mode: ModoExecucao | None = Query(default=None, alias="modo_execucao"),
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            ExecucaoAnaliseModel,
            DatasetModel.nome,
            ModeloDeteccaoModel.nome,
            DatasetModel.total_registros,
        )
        .join(DatasetModel, DatasetModel.id_dataset == ExecucaoAnaliseModel.id_dataset)
        .join(
            ModeloDeteccaoModel,
            ModeloDeteccaoModel.id_modelo == ExecucaoAnaliseModel.id_modelo,
        )
        .filter(ExecucaoAnaliseModel.id_usuario == current_user.id_usuario)
        .order_by(ExecucaoAnaliseModel.criado_em.desc())
    )
    if status_filter is not None:
        query = query.filter(ExecucaoAnaliseModel.status == status_filter)
    if mode is not None:
        query = query.filter(ExecucaoAnaliseModel.modo_execucao == mode)
    return [
        _execution_response(db, execution, dataset_name, model_name, dataset_total)
        for execution, dataset_name, model_name, dataset_total in query.limit(500).all()
    ]


@analyses_router.get("/{execution_id}", response_model=ExecucaoRespostaSchema)
def get_analysis(
    execution_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(
            ExecucaoAnaliseModel,
            DatasetModel.nome,
            ModeloDeteccaoModel.nome,
            DatasetModel.total_registros,
        )
        .join(DatasetModel, DatasetModel.id_dataset == ExecucaoAnaliseModel.id_dataset)
        .join(
            ModeloDeteccaoModel,
            ModeloDeteccaoModel.id_modelo == ExecucaoAnaliseModel.id_modelo,
        )
        .filter(
            ExecucaoAnaliseModel.id_execucao == execution_id,
            ExecucaoAnaliseModel.id_usuario == current_user.id_usuario,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    execution, dataset_name, model_name, dataset_total = row
    return _execution_response(db, execution, dataset_name, model_name, dataset_total)


@analyses_router.post(
    "/{execution_id}/cancelar", status_code=status.HTTP_204_NO_CONTENT
)
def cancel_analysis(
    execution_id: int,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    execution = _owned_execution(db, execution_id, current_user.id_usuario)
    if execution.status not in (
        StatusExecucao.PENDENTE,
        StatusExecucao.EM_ANDAMENTO,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A execução já foi finalizada e não pode ser cancelada",
        )
    execution.status = StatusExecucao.CANCELADA
    execution.finalizada_em = datetime.now(UTC)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@analyses_router.delete("/historico", status_code=status.HTTP_200_OK)
def clear_analysis_history(
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    active_statuses = (
        StatusExecucao.PENDENTE,
        StatusExecucao.EM_ANDAMENTO,
    )
    executions = (
        db.query(ExecucaoAnaliseModel)
        .filter(
            ExecucaoAnaliseModel.id_usuario == current_user.id_usuario,
            ExecucaoAnaliseModel.status.notin_(active_statuses),
        )
        .all()
    )
    if not executions:
        return {
            "removidas": 0,
            "preservadas_em_andamento": db.query(ExecucaoAnaliseModel)
            .filter(
                ExecucaoAnaliseModel.id_usuario == current_user.id_usuario,
                ExecucaoAnaliseModel.status.in_(active_statuses),
            )
            .count(),
        }

    execution_ids = [execution.id_execucao for execution in executions]
    benchmark_ids = [
        row[0]
        for row in db.query(BenchmarkExecucaoModel.id_benchmark)
        .filter(BenchmarkExecucaoModel.id_execucao.in_(execution_ids))
        .distinct()
        .all()
    ]
    if benchmark_ids:
        db.query(BenchmarkModel).filter(
            BenchmarkModel.id_benchmark.in_(benchmark_ids)
        ).delete(synchronize_session=False)

    removed = (
        db.query(ExecucaoAnaliseModel)
        .filter(
            ExecucaoAnaliseModel.id_execucao.in_(execution_ids),
            ExecucaoAnaliseModel.id_usuario == current_user.id_usuario,
        )
        .delete(synchronize_session=False)
    )
    preserved = (
        db.query(ExecucaoAnaliseModel)
        .filter(
            ExecucaoAnaliseModel.id_usuario == current_user.id_usuario,
            ExecucaoAnaliseModel.status.in_(active_statuses),
        )
        .count()
    )
    db.commit()
    return {"removidas": removed, "preservadas_em_andamento": preserved}


@analyses_router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    execution_id: int,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    execution = _owned_execution(db, execution_id, current_user.id_usuario)
    if execution.status in (
        StatusExecucao.PENDENTE,
        StatusExecucao.EM_ANDAMENTO,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uma execução em andamento não pode ser excluída",
        )

    benchmark_ids = [
        row[0]
        for row in db.query(BenchmarkExecucaoModel.id_benchmark)
        .filter(BenchmarkExecucaoModel.id_execucao == execution_id)
        .all()
    ]
    if benchmark_ids:
        db.query(BenchmarkModel).filter(
            BenchmarkModel.id_benchmark.in_(benchmark_ids)
        ).delete(synchronize_session=False)

    db.delete(execution)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@analyses_router.get(
    "/{execution_id}/resultados", response_model=ResultadosPaginaSchema
)
def get_analysis_results(
    execution_id: int,
    pagina: int = Query(default=1, ge=1),
    tamanho_pagina: int = Query(default=25, ge=1, le=200),
    escore_minimo: Decimal | None = Query(default=None, ge=0),
    valor_minimo: Decimal | None = Query(default=None, ge=0),
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    execution = _owned_execution(db, execution_id, current_user.id_usuario)
    query = (
        db.query(ResultadoDeteccaoModel)
        .join(
            TransacaoModel,
            TransacaoModel.id_transacao == ResultadoDeteccaoModel.id_transacao,
        )
        .filter(ResultadoDeteccaoModel.id_execucao == execution_id)
    )
    if escore_minimo is not None:
        query = query.filter(ResultadoDeteccaoModel.score_anomalia >= escore_minimo)
    if valor_minimo is not None:
        query = query.filter(TransacaoModel.valor >= valor_minimo)
    total = query.count()
    rows = (
        query.order_by(
            ResultadoDeteccaoModel.score_anomalia.desc(),
            ResultadoDeteccaoModel.id_transacao,
        )
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
        .all()
    )
    valores = (
        {
            row.id_transacao: row.valor
            for row in db.query(TransacaoModel)
            .filter(
                TransacaoModel.id_transacao.in_([item.id_transacao for item in rows])
            )
            .all()
        }
        if rows
        else {}
    )
    metric = db.query(MetricaExecucaoModel).filter_by(id_execucao=execution_id).first()
    return ResultadosPaginaSchema(
        execucao=_execution_response(db, execution),
        metrica=(
            MetricaRespostaSchema.model_validate(metric)
            if metric is not None
            else MetricaRespostaSchema()
        ),
        itens=[
            ResultadoRespostaSchema(
                id_resultado=item.id_resultado,
                id_execucao=item.id_execucao,
                id_transacao=item.id_transacao,
                score_anomalia=item.score_anomalia,
                is_suspeita=item.is_suspeita,
                limiar_aplicado=item.limiar_aplicado,
                chunk_id=item.chunk_id,
                valor=valores.get(item.id_transacao),
            )
            for item in rows
        ],
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
    )


@analyses_router.get("/{execution_id}/resultados/exportar")
def export_analysis_results(
    execution_id: int,
    formato: Literal["csv", "json", "pdf"] = Query(...),
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_execution(db, execution_id, current_user.id_usuario)
    headers = {
        "Content-Disposition": f'attachment; filename="analise-{execution_id}.{formato}"'
    }
    if formato == "json":
        return StreamingResponse(
            _stream_json_results(execution_id),
            media_type="application/json",
            headers=headers,
        )
    if formato == "csv":
        return StreamingResponse(
            _stream_csv_results(execution_id),
            media_type="text/csv; charset=utf-8",
            headers=headers,
        )
    return Response(
        _render_analysis_pdf(execution_id),
        media_type="application/pdf",
        headers=headers,
    )


@analyses_router.get(
    "/{execution_id}/resultados/{transaction_id}",
    response_model=DetalheResultadoSchema,
)
def get_transaction_result(
    execution_id: int,
    transaction_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    execution = _owned_execution(db, execution_id, current_user.id_usuario)
    current_result = (
        db.query(ResultadoDeteccaoModel)
        .filter_by(id_execucao=execution_id, id_transacao=transaction_id)
        .first()
    )
    if current_result is None:
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    transaction = (
        db.query(TransacaoModel)
        .filter_by(id_transacao=transaction_id, id_dataset=execution.id_dataset)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    history_rows = (
        db.query(ExecucaoAnaliseModel, ResultadoDeteccaoModel)
        .join(
            ResultadoDeteccaoModel,
            ResultadoDeteccaoModel.id_execucao == ExecucaoAnaliseModel.id_execucao,
        )
        .filter(
            ExecucaoAnaliseModel.id_usuario == current_user.id_usuario,
            ExecucaoAnaliseModel.id_dataset == execution.id_dataset,
            ExecucaoAnaliseModel.id_modelo == execution.id_modelo,
            ResultadoDeteccaoModel.id_transacao == transaction_id,
        )
        .order_by(ExecucaoAnaliseModel.criado_em.asc())
        .all()
    )
    baseline_score = next(
        (
            result.score_anomalia
            for previous, result in history_rows
            if previous.modo_execucao == ModoExecucao.SEQUENCIAL
        ),
        None,
    )
    history = [
        AvaliacaoHistoricoSchema(
            id_execucao=previous.id_execucao,
            modo_execucao=previous.modo_execucao,
            work_group_size=previous.num_workers,
            score_calculado=result.score_anomalia,
            equivalente_ao_baseline=(
                bool(
                    np.isclose(
                        float(result.score_anomalia),
                        float(baseline_score),
                        rtol=1e-5,
                        atol=1e-6,
                    )
                )
                if baseline_score is not None
                else None
            ),
        )
        for previous, result in history_rows
    ]
    return DetalheResultadoSchema(
        transacao=TransacaoDetalheSchema.model_validate(transaction),
        resultado_atual=ResultadoAtualSchema(
            id_execucao=execution_id,
            score_anomalia=current_result.score_anomalia,
            limiar_aplicado=current_result.limiar_aplicado,
            is_suspeita=current_result.is_suspeita,
        ),
        historico=history,
    )


def _result_export_query(db: Session, execution_id: int):
    return (
        db.query(ResultadoDeteccaoModel, TransacaoModel)
        .join(
            TransacaoModel,
            TransacaoModel.id_transacao == ResultadoDeteccaoModel.id_transacao,
        )
        .filter(ResultadoDeteccaoModel.id_execucao == execution_id)
        .order_by(ResultadoDeteccaoModel.score_anomalia.desc())
        .yield_per(1000)
    )


def _result_export_record(
    result: ResultadoDeteccaoModel, transaction: TransacaoModel
) -> dict[str, object]:
    return {
        "id_execucao": result.id_execucao,
        "id_transacao": result.id_transacao,
        "indice_origem": transaction.indice_origem,
        "score_anomalia": float(result.score_anomalia),
        "is_suspeita": result.is_suspeita,
        "limiar_aplicado": float(result.limiar_aplicado),
        "chunk_id": result.chunk_id,
        "valor": float(transaction.valor) if transaction.valor is not None else None,
        "tempo_relativo": (
            float(transaction.tempo_relativo)
            if transaction.tempo_relativo is not None
            else None
        ),
        "rotulo_real": transaction.rotulo_real,
        "atributos": transaction.atributos,
    }


def _stream_json_results(execution_id: int):
    db = SessionLocal()
    try:
        yield "["
        for index, (result, transaction) in enumerate(
            _result_export_query(db, execution_id)
        ):
            if index:
                yield ","
            yield json.dumps(
                _result_export_record(result, transaction), ensure_ascii=False
            )
        yield "]"
    finally:
        db.close()


def _stream_csv_results(execution_id: int):
    fieldnames = [
        "id_execucao",
        "id_transacao",
        "indice_origem",
        "score_anomalia",
        "is_suspeita",
        "limiar_aplicado",
        "chunk_id",
        "valor",
        "tempo_relativo",
        "rotulo_real",
        "atributos",
    ]
    db = SessionLocal()
    try:
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        for result, transaction in _result_export_query(db, execution_id):
            record = _result_export_record(result, transaction)
            record["atributos"] = json.dumps(record["atributos"], ensure_ascii=False)
            writer.writerow(record)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
    finally:
        db.close()


def _render_analysis_pdf(execution_id: int) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    content = [
        Paragraph(f"Resultados da análise #{execution_id}", styles["Title"]),
        Spacer(1, 5 * mm),
    ]

    table_data = [
        [
            "ID transação",
            "Índice",
            "Score",
            "Suspeita",
            "Limiar",
            "Valor",
            "Tempo relativo",
        ]
    ]
    db = SessionLocal()
    try:
        count = 0
        for result, transaction in _result_export_query(db, execution_id):
            count += 1
            table_data.append(
                [
                    str(result.id_transacao),
                    str(transaction.indice_origem),
                    f"{float(result.score_anomalia):.6f}",
                    "Sim" if result.is_suspeita else "Não",
                    f"{float(result.limiar_aplicado):.6f}",
                    (
                        f"{float(transaction.valor):.2f}"
                        if transaction.valor is not None
                        else "N/D"
                    ),
                    (
                        f"{float(transaction.tempo_relativo):.2f}"
                        if transaction.tempo_relativo is not None
                        else "N/D"
                    ),
                ]
            )
        content.insert(
            1,
            Paragraph(
                f"Total de resultados: {escape(str(count))}",
                styles["Normal"],
            ),
        )
    finally:
        db.close()

    table = Table(table_data, repeatRows=1, hAlign="LEFT")
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
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    content.append(table)
    document.build(content)
    return buffer.getvalue()


@models_router.get("", response_model=list[ModeloRespostaSchema])
def list_detection_models(
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del current_user
    return (
        db.query(ModeloDeteccaoModel)
        .filter(ModeloDeteccaoModel.algoritmo == TipoAlgoritmo.ISOLATION_FOREST)
        .order_by(ModeloDeteccaoModel.id_modelo)
        .all()
    )


def _owned_execution(db: Session, execution_id: int, owner_id: int):
    execution = (
        db.query(ExecucaoAnaliseModel)
        .filter(
            ExecucaoAnaliseModel.id_execucao == execution_id,
            ExecucaoAnaliseModel.id_usuario == owner_id,
        )
        .first()
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return execution


def _execution_response(
    db: Session,
    execution: ExecucaoAnaliseModel,
    dataset_name: str | None = None,
    model_name: str | None = None,
    dataset_total: int | None = None,
) -> ExecucaoRespostaSchema:
    if dataset_name is None or model_name is None or dataset_total is None:
        metadata = (
            db.query(
                DatasetModel.nome,
                ModeloDeteccaoModel.nome,
                DatasetModel.total_registros,
            )
            .join(
                ModeloDeteccaoModel,
                ModeloDeteccaoModel.id_modelo == execution.id_modelo,
            )
            .filter(DatasetModel.id_dataset == execution.id_dataset)
            .first()
        )
        dataset_name = metadata[0] if metadata is not None else None
        model_name = metadata[1] if metadata is not None else None
        dataset_total = metadata[2] if metadata is not None else 0
    progress = (
        100
        if execution.status == StatusExecucao.CONCLUIDA
        else int(100 * execution.total_analisadas / max(dataset_total or 1, 1))
    )
    return ExecucaoRespostaSchema(
        id_execucao=execution.id_execucao,
        id_dataset=execution.id_dataset,
        id_modelo=execution.id_modelo,
        dataset_nome=dataset_name,
        modelo_nome=model_name,
        modo_execucao=execution.modo_execucao,
        work_group_size=execution.num_workers,
        tipo_dispositivo=execution.tipo_dispositivo,
        tamanho_chunk=execution.tamanho_chunk,
        limiar_aplicado=execution.limiar_aplicado,
        status=execution.status,
        progresso_percentual=min(progress, 100),
        iniciada_em=execution.iniciada_em,
        finalizada_em=execution.finalizada_em,
        tempo_total_s=execution.tempo_total_s,
        total_analisadas=execution.total_analisadas,
        total_registros=dataset_total or 0,
        total_suspeitas=execution.total_suspeitas,
        mensagem_erro=execution.mensagem_erro,
        criado_em=execution.criado_em,
    )
