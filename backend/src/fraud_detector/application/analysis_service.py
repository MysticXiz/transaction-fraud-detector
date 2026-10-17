from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal

import numpy as np
import pandas as pd
import psutil
from sqlalchemy import insert
from sqlalchemy.orm import Session

from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLDeviceType,
    OpenCLIsolationForestExecutor,
)
from src.fraud_detector.computational.preprocessing.preprocessor import Preprocessor
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import SessionLocal
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.detection_model import (
    ModeloDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.execution import (
    ExecucaoAnaliseModel,
    MetricaExecucaoModel,
    ResultadoDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel

logger = logging.getLogger("fraud_detector.analysis")
DEFAULT_CHUNK_SIZE = 10_000
_ANALYSIS_LOCK = threading.Lock()


class AnalysisRequestError(ValueError):
    pass


class AnalysisNotFoundError(AnalysisRequestError):
    pass


class _ResourceSampler:
    def __init__(self) -> None:
        self._process = psutil.Process()
        self._stop = threading.Event()
        self._peak_memory_bytes = self._process.memory_info().rss
        self._started_at = 0.0
        self._started_cpu_seconds = 0.0
        self._average_cpu_percent: float | None = None
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def __enter__(self) -> _ResourceSampler:
        self._started_at = perf_counter()
        cpu_times = self._process.cpu_times()
        self._started_cpu_seconds = cpu_times.user + cpu_times.system
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self._record_sample()
        elapsed = perf_counter() - self._started_at
        cpu_times = self._process.cpu_times()
        cpu_seconds = cpu_times.user + cpu_times.system - self._started_cpu_seconds
        if elapsed > 0:
            self._average_cpu_percent = min(
                max(cpu_seconds, 0.0) / elapsed / max(psutil.cpu_count() or 1, 1) * 100,
                100.0,
            )

    def _sample(self) -> None:
        while not self._stop.wait(0.1):
            self._record_sample()

    def _record_sample(self) -> None:
        self._peak_memory_bytes = max(
            self._peak_memory_bytes, self._process.memory_info().rss
        )

    @property
    def average_cpu_percent(self) -> float | None:
        return self._average_cpu_percent

    @property
    def peak_memory_mb(self) -> float:
        return self._peak_memory_bytes / (1024 * 1024)


def create_execution(
    db: Session,
    *,
    owner_id: int,
    dataset_id: int,
    model_id: int,
    mode: ModoExecucao,
    workers: int,
    device_type: OpenCLDeviceType | None,
    chunk_size: int | None,
    threshold: Decimal | None,
) -> ExecucaoAnaliseModel:
    dataset = (
        db.query(DatasetModel)
        .filter(
            DatasetModel.id_dataset == dataset_id,
            DatasetModel.id_usuario == owner_id,
        )
        .first()
    )
    if dataset is None:
        raise AnalysisNotFoundError("Dataset não encontrado")
    model = db.query(ModeloDeteccaoModel).filter_by(id_modelo=model_id).first()
    model = _validate_supported_model(model)
    if mode == ModoExecucao.SEQUENCIAL and workers != 1:
        raise AnalysisRequestError(
            "A execução sequencial deve usar exatamente um worker"
        )
    if dataset.total_registros < 2:
        raise AnalysisRequestError(
            "A detecção Isolation Forest exige ao menos duas transações"
        )

    execution = ExecucaoAnaliseModel(
        id_dataset=dataset_id,
        id_modelo=model_id,
        id_usuario=owner_id,
        modo_execucao=mode,
        num_workers=workers,
        tipo_dispositivo=device_type,
        tamanho_chunk=chunk_size or DEFAULT_CHUNK_SIZE,
        limiar_aplicado=threshold if threshold is not None else model.limiar_padrao,
        status=StatusExecucao.PENDENTE,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _validate_supported_model(
    model: ModeloDeteccaoModel | None,
) -> ModeloDeteccaoModel:
    if model is None:
        raise AnalysisNotFoundError("Modelo de detecção não encontrado")
    if model.algoritmo != TipoAlgoritmo.ISOLATION_FOREST:
        raise AnalysisRequestError(
            "No momento, execuções estão disponíveis apenas para Isolation Forest"
        )
    return model


def run_execution(
    db: Session,
    execution_id: int,
    *,
    opencl_device_type: OpenCLDeviceType | None = None,
) -> None:
    with _ANALYSIS_LOCK:
        _run_execution(db, execution_id, opencl_device_type=opencl_device_type)


def _run_execution(
    db: Session,
    execution_id: int,
    *,
    opencl_device_type: OpenCLDeviceType | None = None,
) -> None:
    execution = (
        db.query(ExecucaoAnaliseModel)
        .filter_by(id_execucao=execution_id)
        .populate_existing()
        .first()
    )
    if execution is None or execution.status != StatusExecucao.PENDENTE:
        return

    execution.status = StatusExecucao.EM_ANDAMENTO
    execution.iniciada_em = datetime.now(UTC)
    db.commit()
    started = perf_counter()
    read_seconds = 0.0
    preprocessing_seconds = 0.0
    inference_seconds = 0.0
    total_analyzed = 0
    total_suspicious = 0
    sampler = _ResourceSampler()

    try:
        with sampler:
            read_started = perf_counter()
            rows = (
                db.query(TransacaoModel)
                .filter(TransacaoModel.id_dataset == execution.id_dataset)
                .order_by(TransacaoModel.indice_origem)
                .all()
            )
            read_seconds = perf_counter() - read_started
            if len(rows) < 2:
                raise ValueError(
                    "A detecção Isolation Forest exige ao menos duas transações"
                )

            frame = _transactions_frame(rows)
            prep_started = perf_counter()
            preprocessor = Preprocessor()
            features = preprocessor.fit_transform(frame)
            preprocessing_seconds = perf_counter() - prep_started

            model = (
                db.query(ModeloDeteccaoModel)
                .filter_by(id_modelo=execution.id_modelo)
                .first()
            )
            model = _validate_supported_model(model)
            executor = _create_executor(
                model.hiperparametros or {},
                opencl_device_type=(
                    opencl_device_type or execution.tipo_dispositivo
                ),
            )

            inference_started = perf_counter()
            executor.fit(features)
            threshold = float(execution.limiar_aplicado)
            chunk_size = execution.tamanho_chunk or DEFAULT_CHUNK_SIZE
            work_group_size = (
                execution.num_workers
                if execution.modo_execucao == ModoExecucao.PARALELO
                else None
            )

            for chunk_id, start in enumerate(range(0, len(rows), chunk_size)):
                current = (
                    db.query(ExecucaoAnaliseModel)
                    .filter_by(id_execucao=execution_id)
                    .populate_existing()
                    .first()
                )
                if current is None or current.status == StatusExecucao.CANCELADA:
                    break
                end = min(start + chunk_size, len(rows))
                chunk_features = features[start:end]
                if execution.modo_execucao == ModoExecucao.PARALELO:
                    scores = executor.score_opencl(
                        chunk_features, work_group_size=work_group_size
                    )
                else:
                    scores = executor.score_sequential(chunk_features)
                suspicious = np.asarray(scores) >= threshold
                mappings = [
                    {
                        "id_execucao": execution_id,
                        "id_transacao": rows[index].id_transacao,
                        "score_anomalia": float(scores[offset]),
                        "is_suspeita": bool(suspicious[offset]),
                        "limiar_aplicado": threshold,
                        "chunk_id": chunk_id,
                    }
                    for offset, index in enumerate(range(start, end))
                ]
                db.execute(insert(ResultadoDeteccaoModel), mappings)
                total_analyzed += len(mappings)
                total_suspicious += int(suspicious.sum())
                current.total_analisadas = total_analyzed
                current.total_suspeitas = total_suspicious
                db.commit()

            inference_seconds = perf_counter() - inference_started

        _finish_execution(
            db,
            execution_id=execution_id,
            total_analyzed=total_analyzed,
            total_suspicious=total_suspicious,
            total_seconds=perf_counter() - started,
            read_seconds=read_seconds,
            preprocessing_seconds=preprocessing_seconds,
            inference_seconds=inference_seconds,
            sampler=sampler,
        )
    except Exception as error:
        db.rollback()
        logger.exception("Falha ao executar análise %s", execution_id)
        current = (
            db.query(ExecucaoAnaliseModel)
            .filter_by(id_execucao=execution_id)
            .populate_existing()
            .first()
        )
        if current is not None:
            if current.status != StatusExecucao.CANCELADA:
                current.status = StatusExecucao.FALHA
                current.mensagem_erro = str(error)[:2000]
            current.finalizada_em = datetime.now(UTC)
            current.tempo_total_s = Decimal(str(perf_counter() - started))
            current.total_analisadas = total_analyzed
            current.total_suspeitas = total_suspicious
            db.commit()
        _save_metrics(
            db,
            execution_id,
            read_seconds,
            preprocessing_seconds,
            inference_seconds,
            perf_counter() - started,
            sampler,
            total_analyzed,
        )
        db.commit()


def run_execution_in_background(execution_id: int) -> None:
    db = SessionLocal()
    try:
        run_execution(db, execution_id)
    finally:
        db.close()


def _transactions_frame(rows: list[TransacaoModel]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row.atributos or {})
        record["Time"] = (
            float(row.tempo_relativo) if row.tempo_relativo is not None else None
        )
        record["Amount"] = float(row.valor) if row.valor is not None else None
        records.append(record)
    return pd.DataFrame.from_records(records)


def _create_executor(
    parameters: dict[str, Any],
    *,
    opencl_device_type: OpenCLDeviceType | None = None,
) -> OpenCLIsolationForestExecutor:
    n_estimators = parameters.get("n_estimators", 200)
    contamination = parameters.get("contamination", 0.0017)
    random_state = parameters.get("random_state", 42)
    if not isinstance(n_estimators, int) or not 1 <= n_estimators <= 2000:
        raise ValueError("O modelo possui um n_estimators inválido")
    if contamination == "auto":
        contamination_value: float | Literal["auto"] = "auto"
    elif isinstance(contamination, (int, float)) and 0 < contamination <= 0.5:
        contamination_value = float(contamination)
    else:
        raise ValueError("O modelo possui um contamination inválido")
    if not isinstance(random_state, int):
        raise ValueError("O modelo possui um random_state inválido")
    return OpenCLIsolationForestExecutor(
        n_estimators=n_estimators,
        contamination=contamination_value,
        random_state=random_state,
        device_type=opencl_device_type,
    )


def _finish_execution(
    db: Session,
    *,
    execution_id: int,
    total_analyzed: int,
    total_suspicious: int,
    total_seconds: float,
    read_seconds: float,
    preprocessing_seconds: float,
    inference_seconds: float,
    sampler: _ResourceSampler,
) -> None:
    execution = (
        db.query(ExecucaoAnaliseModel)
        .filter_by(id_execucao=execution_id)
        .populate_existing()
        .first()
    )
    if execution is None:
        return
    was_cancelled = execution.status == StatusExecucao.CANCELADA
    if not was_cancelled:
        execution.status = StatusExecucao.CONCLUIDA
    execution.finalizada_em = datetime.now(UTC)
    execution.tempo_total_s = Decimal(str(total_seconds))
    execution.total_analisadas = total_analyzed
    execution.total_suspeitas = total_suspicious
    _save_metrics(
        db,
        execution_id,
        read_seconds,
        preprocessing_seconds,
        inference_seconds,
        total_seconds,
        sampler,
        total_analyzed,
    )
    db.commit()


def _save_metrics(
    db: Session,
    execution_id: int,
    read_seconds: float,
    preprocessing_seconds: float,
    inference_seconds: float,
    total_seconds: float,
    sampler: _ResourceSampler,
    total_analyzed: int,
) -> None:
    metric = db.query(MetricaExecucaoModel).filter_by(id_execucao=execution_id).first()
    if metric is None:
        metric = MetricaExecucaoModel(id_execucao=execution_id)
        db.add(metric)
    overhead = max(
        total_seconds - read_seconds - preprocessing_seconds - inference_seconds, 0.0
    )
    metric.tempo_leitura_s = Decimal(str(read_seconds))
    metric.tempo_preproc_s = Decimal(str(preprocessing_seconds))
    metric.tempo_inferencia_s = Decimal(str(inference_seconds))
    metric.tempo_overhead_s = Decimal(str(overhead))
    metric.cpu_percent_medio = (
        Decimal(str(sampler.average_cpu_percent))
        if sampler.average_cpu_percent is not None
        else None
    )
    metric.memoria_pico_mb = Decimal(str(sampler.peak_memory_mb))
    metric.throughput_tps = (
        Decimal(str(total_analyzed / total_seconds)) if total_seconds > 0 else None
    )
    metric.nucleos_disponiveis = psutil.cpu_count() or 1
