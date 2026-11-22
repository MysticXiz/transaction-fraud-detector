from __future__ import annotations

import logging
import threading
import queue
import struct
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from time import perf_counter
from typing import Any, Literal

import numpy as np
import pandas as pd
import psutil
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLDeviceType,
    OpenCLExecutionError,
    OpenCLIsolationForestExecutor,
    OpenCLRuntimeUnavailableError,
    available_cpu_capacity,
)
from src.fraud_detector.computational.preprocessing.preprocessor import Preprocessor
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_stage import EtapaExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import SessionLocal
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.detection_model import (
    ModeloDeteccaoModel,
)
from src.fraud_detector.infrastructure.models.execution import (
    ExecucaoAnaliseModel,
    MetricaExecucaoModel,
)
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel

logger = logging.getLogger("fraud_detector.analysis")
DEFAULT_CHUNK_SIZE = 50_000
_WRITER_STOP = object()
_execution_stages: dict[int, EtapaExecucao] = {}


def get_execution_stage(execution_id: int) -> EtapaExecucao | None:
    return _execution_stages.get(execution_id)


def _result_writer_count() -> int:
    return max(1, min(4, available_cpu_capacity()))


@dataclass(frozen=True, slots=True)
class _ResultWriterItem:
    execution_id: int
    transaction_ids: NDArray[np.int64]
    scores: NDArray[np.float32]
    suspicious: NDArray[np.bool_]
    threshold: float
    chunk_id: int


def _create_result_writer_item(
    execution_id: int,
    transaction_ids: NDArray[np.int64],
    scores: NDArray[np.number],
    threshold: float,
    chunk_id: int,
) -> tuple[_ResultWriterItem, NDArray[np.bool_]]:
    chunk_scores = np.asarray(scores, dtype=np.float32)
    chunk_suspicious = np.asarray(chunk_scores >= threshold, dtype=np.bool_)
    return (
        _ResultWriterItem(
            execution_id=execution_id,
            transaction_ids=transaction_ids,
            scores=chunk_scores,
            suspicious=chunk_suspicious,
            threshold=threshold,
            chunk_id=chunk_id,
        ),
        chunk_suspicious,
    )


class AnalysisRequestError(ValueError):
    pass


class AnalysisNotFoundError(AnalysisRequestError):
    pass


def _encode_numeric_binary(value: float | Decimal, scale: int) -> bytes:
    decimal_value = Decimal(str(value)).quantize(Decimal(1).scaleb(-scale))
    if decimal_value == 0:
        return struct.pack(">hhhh", 0, 0, 0, scale)

    sign = 0x4000 if decimal_value.is_signed() else 0x0000
    decimal_value = abs(decimal_value)
    fixed = format(decimal_value, f".{scale}f")
    integer_text, fractional_text = fixed.split(".", 1)
    integer_text = integer_text.lstrip("0") or ""

    if integer_text:
        weight = (len(integer_text) - 1) // 4
        integer_width = (weight + 1) * 4
        coefficient = integer_text.rjust(integer_width, "0")
        coefficient += fractional_text.ljust(
            ((len(fractional_text) + 3) // 4) * 4,
            "0",
        )
    else:
        weight = -1
        coefficient = fractional_text.ljust(
            ((len(fractional_text) + 3) // 4) * 4,
            "0",
        )

    groups = [
        int(coefficient[position : position + 4])
        for position in range(0, len(coefficient), 4)
    ]
    while len(groups) > 1 and groups[-1] == 0:
        groups.pop()

    return struct.pack(">hhhh", len(groups), weight, sign, scale) + b"".join(
        struct.pack(">H", group) for group in groups
    )


def _encode_binary_copy_batch(item: _ResultWriterItem) -> bytes:
    header = b"PGCOPY\n\xff\r\n\x00" + struct.pack(">II", 0, 0)
    row_count = len(item.transaction_ids)
    threshold = Decimal(str(item.threshold)).quantize(Decimal("0.0001"))
    threshold_binary = _encode_numeric_binary(threshold, 4)
    execution_ids = np.full(row_count, item.execution_id, dtype=np.int32)
    transaction_ids = np.ascontiguousarray(item.transaction_ids, dtype=np.int64)
    suspicious = np.ascontiguousarray(item.suspicious, dtype=np.bool_)
    chunk_ids = np.full(row_count, item.chunk_id, dtype=np.int32)
    scores = np.ascontiguousarray(item.scores, dtype=np.float32)

    body = bytearray()
    for row in range(row_count):
        fields = (
            int(execution_ids[row]).to_bytes(4, "big", signed=True),
            int(transaction_ids[row]).to_bytes(8, "big", signed=True),
            _encode_numeric_binary(float(scores[row]), 6),
            b"\x01" if suspicious[row] else b"\x00",
            threshold_binary,
            int(chunk_ids[row]).to_bytes(4, "big", signed=True),
        )
        lengths = (
            4,
            8,
            len(fields[2]),
            1,
            len(fields[4]),
            4,
        )
        body.extend(struct.pack(">h", len(fields)))
        for length, value in zip(lengths, fields, strict=True):
            if length != len(value):
                body.extend(struct.pack(">i", len(value)))
            else:
                body.extend(struct.pack(">i", length))
            body.extend(value)

    return header + bytes(body) + struct.pack(">h", -1)


def _result_writer(
    write_queue: queue.Queue[_ResultWriterItem | object],
    writer_errors: list[BaseException],
    writer_lock: threading.Lock | None = None,
) -> None:
    writer_db = SessionLocal()
    lock = writer_lock or threading.Lock()
    try:
        while True:
            item = write_queue.get()
            if item is _WRITER_STOP:
                write_queue.task_done()
                return
            if writer_errors:
                write_queue.task_done()
                continue
            try:
                connection = writer_db.connection().connection
                raw_connection = getattr(connection, "driver_connection", connection)
                with raw_connection.cursor() as cursor:
                    with cursor.copy(
                        "COPY resultado_deteccao "
                        "(id_execucao, id_transacao, score_anomalia, "
                        "is_suspeita, limiar_aplicado, chunk_id) "
                        "FROM STDIN WITH (FORMAT BINARY)"
                    ) as copy:
                        copy.set_types(
                            ("int4", "int8", "numeric", "bool", "numeric", "int4")
                        )
                        copy.write(_encode_binary_copy_batch(item))
                writer_db.commit()
            except BaseException as error:
                writer_db.rollback()
                with lock:
                    if not writer_errors:
                        writer_errors.append(error)
                logger.exception("Falha ao persistir lote de resultados")
                return
            finally:
                write_queue.task_done()
    finally:
        writer_db.close()


class _ResourceSampler:
    def __init__(self) -> None:
        self._process = psutil.Process()
        self.cpu_capacity = available_cpu_capacity()
        self._stop = threading.Event()
        self._peak_memory_bytes = self._process.memory_info().rss
        self._started_at = 0.0
        self._started_cpu_seconds = 0.0
        self._average_cpu_percent: float | None = None
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def __enter__(self) -> _ResourceSampler:
        self._started_at = perf_counter()
        self._started_cpu_seconds = self.cpu_seconds()
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self._record_sample()
        self._average_cpu_percent = self.cpu_percent_since(
            self._started_at, self._started_cpu_seconds
        )

    def cpu_seconds(self) -> float:
        cpu_times = self._process.cpu_times()
        return cpu_times.user + cpu_times.system

    def cpu_percent_since(self, started_at: float, started_cpu_seconds: float) -> float:
        elapsed = perf_counter() - started_at
        if elapsed <= 0:
            return 0.0
        cpu_seconds = self.cpu_seconds() - started_cpu_seconds
        return min(max(cpu_seconds, 0.0) / elapsed / self.cpu_capacity * 100.0, 100.0)

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
    work_group_size: int | None,
    device_type: OpenCLDeviceType | None,
    chunk_size: int | None,
    threshold: Decimal | None,
    commit: bool = True,
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
    if mode == ModoExecucao.SEQUENCIAL and work_group_size not in (None, 1):
        raise AnalysisRequestError(
            "A execução sequencial deve usar exatamente um worker"
        )
    if mode == ModoExecucao.PARALELO and device_type is not None:
        recommendation = OpenCLIsolationForestExecutor.recommend_for_device(
            device_type,
            dataset_size=dataset.total_registros or 50_000,
        )
        recommended_work_group = int(recommendation["work_group_recomendado"])
        recommended_chunk = int(recommendation["chunk_recomendado"])
        if work_group_size is None:
            work_group_size = recommended_work_group
        if work_group_size > int(recommendation["max_work_group_size"]):
            raise AnalysisRequestError(
                "O tamanho do work-group excede o limite do dispositivo OpenCL"
            )
        if chunk_size is None:
            chunk_size = recommended_chunk
    elif mode == ModoExecucao.SEQUENCIAL:
        work_group_size = 1
    if dataset.total_registros < 2:
        raise AnalysisRequestError(
            "A detecção Isolation Forest exige ao menos duas transações"
        )

    execution = ExecucaoAnaliseModel(
        id_dataset=dataset_id,
        id_modelo=model_id,
        id_usuario=owner_id,
        modo_execucao=mode,
        num_workers=work_group_size,
        tipo_dispositivo=device_type,
        tamanho_chunk=chunk_size or DEFAULT_CHUNK_SIZE,
        limiar_aplicado=threshold if threshold is not None else model.limiar_padrao,
        status=StatusExecucao.PENDENTE,
    )
    db.add(execution)
    if commit:
        db.commit()
        db.refresh(execution)
    else:
        db.flush()
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
    for_benchmark: bool = False,
) -> None:
    execution = (
        db.query(ExecucaoAnaliseModel)
        .filter_by(id_execucao=execution_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if execution is None or execution.status != StatusExecucao.PENDENTE:
        db.rollback()
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
    writer_queue: queue.Queue[_ResultWriterItem | object] | None = None
    writer_threads: list[threading.Thread] = []
    writer_errors: list[BaseException] = []
    writer_lock = threading.Lock()

    try:
        with sampler:
            _execution_stages[execution_id] = EtapaExecucao.LEITURA
            read_started = perf_counter()
            statement = (
                select(
                    TransacaoModel.id_transacao,
                    TransacaoModel.tempo_relativo,
                    TransacaoModel.valor,
                    TransacaoModel.atributos,
                )
                .where(TransacaoModel.id_dataset == execution.id_dataset)
                .order_by(TransacaoModel.indice_origem)
            )
            frame_parts = []
            transaction_id_parts = []
            frame_build_seconds = 0.0
            # Chaves JSON são strings. Rótulos inteiros evitam colisões nos lotes.
            time_column, amount_column = 0, 1
            with db.execute(statement.execution_options(yield_per=5000)) as result:
                for rows in result.partitions(5000):
                    frame_started = perf_counter()
                    transaction_id_parts.append(
                        np.fromiter(
                            (row.id_transacao for row in rows),
                            dtype=np.int64,
                            count=len(rows),
                        )
                    )
                    frame_parts.append(
                        _transactions_frame(
                            rows, measure_columns=(time_column, amount_column)
                        )
                    )
                    frame_build_seconds += perf_counter() - frame_started
                    del rows
            db.commit()
            read_seconds = perf_counter() - read_started - frame_build_seconds
            if sum(len(part) for part in transaction_id_parts) < 2:
                raise ValueError(
                    "A detecção Isolation Forest exige ao menos duas transações"
                )
            _execution_stages[execution_id] = EtapaExecucao.PRE_PROCESSAMENTO
            transaction_ids = np.concatenate(transaction_id_parts)
            del transaction_id_parts
            sample_count = len(transaction_ids)
            prep_started = perf_counter()
            frame = pd.concat(frame_parts, ignore_index=True, sort=False)
            del frame_parts
            frame["Time"] = frame.pop(time_column)
            frame["Amount"] = frame.pop(amount_column)
            preprocessor = Preprocessor()
            features = preprocessor.fit_transform(frame)
            del frame
            preprocessing_seconds = perf_counter() - prep_started + frame_build_seconds

            model = (
                db.query(ModeloDeteccaoModel)
                .filter_by(id_modelo=execution.id_modelo)
                .first()
            )
            model = _validate_supported_model(model)
            parallel = execution.modo_execucao == ModoExecucao.PARALELO
            training_jobs = sampler.cpu_capacity if parallel else 1
            executor = _create_executor(
                model.hiperparametros or {},
                opencl_device_type=(opencl_device_type or execution.tipo_dispositivo),
                training_jobs=training_jobs,
            )

            _execution_stages[execution_id] = EtapaExecucao.TREINAMENTO
            fit_started = perf_counter()
            fit_cpu_started = sampler.cpu_seconds()
            executor.fit(features)
            logger.info(
                "Análise %s: treinamento em %.3fs, até %s de %s threads, %.1f%% de CPU",
                execution_id,
                perf_counter() - fit_started,
                training_jobs,
                sampler.cpu_capacity,
                sampler.cpu_percent_since(fit_started, fit_cpu_started),
            )
            threshold = float(execution.limiar_aplicado)
            chunk_size = execution.tamanho_chunk or DEFAULT_CHUNK_SIZE
            work_group_size = (
                execution.num_workers
                if execution.modo_execucao == ModoExecucao.PARALELO
                else None
            )
            score_chunk: Callable[[NDArray[np.number]], NDArray[np.floating]] = (
                executor.score_sequential
            )
            if for_benchmark and execution.modo_execucao == ModoExecucao.PARALELO:
                score_chunk = partial(
                    executor.score_opencl, work_group_size=work_group_size
                )

            inference_seconds = 0.0
            writer_count = _result_writer_count()
            writer_queue = queue.Queue(maxsize=2 * writer_count)
            for worker_id in range(writer_count):
                writer_thread = threading.Thread(
                    target=_result_writer,
                    args=(writer_queue, writer_errors, writer_lock),
                    name=f"result-writer-{execution_id}-{worker_id}",
                    daemon=True,
                )
                writer_thread.start()
                writer_threads.append(writer_thread)
            pending_opencl: tuple[Any, int, int, int] | None = None
            _execution_stages[execution_id] = EtapaExecucao.INFERENCIA
            scoring_started = perf_counter()
            scoring_cpu_started = sampler.cpu_seconds()
            for chunk_id, start in enumerate(range(0, sample_count, chunk_size)):
                current = (
                    db.query(ExecucaoAnaliseModel)
                    .filter_by(id_execucao=execution_id)
                    .populate_existing()
                    .first()
                )
                if current is None or current.status == StatusExecucao.CANCELADA:
                    break
                end = min(start + chunk_size, sample_count)
                chunk_features = features[start:end]

                if for_benchmark or execution.modo_execucao == ModoExecucao.SEQUENCIAL:
                    if for_benchmark and chunk_id == 0:
                        # Aquece ambos os modos antes da medição, incluindo o runtime OpenCL.
                        score_chunk(chunk_features)
                    inference_chunk_started = perf_counter()
                    scores = score_chunk(chunk_features)
                    inference_seconds += perf_counter() - inference_chunk_started
                    writer_item, suspicious = _create_result_writer_item(
                        execution_id,
                        transaction_ids[start:end],
                        scores,
                        threshold,
                        chunk_id,
                    )
                    if writer_errors:
                        raise RuntimeError(
                            "Falha ao persistir resultados da análise"
                        ) from writer_errors[0]
                    writer_queue.put(writer_item)
                    total_analyzed += len(writer_item.transaction_ids)
                    total_suspicious += int(suspicious.sum())
                else:
                    try:
                        current_pending = executor.submit_opencl(
                            chunk_features,
                            work_group_size=work_group_size,
                            chunk_id=chunk_id,
                        )
                    except (
                        OpenCLExecutionError,
                        OpenCLRuntimeUnavailableError,
                    ) as error:
                        logger.warning(
                            "Falha OpenCL na execução %s; usando CPU: %s",
                            execution_id,
                            error,
                        )
                        current_pending = None

                    if pending_opencl is not None:
                        (
                            previous_pending,
                            previous_start,
                            previous_end,
                            previous_chunk_id,
                        ) = pending_opencl
                        scores = executor.collect_opencl(previous_pending)
                        inference_seconds += (
                            executor.last_kernel_seconds
                            + executor.last_transfer_seconds
                        )
                        writer_item, previous_suspicious = _create_result_writer_item(
                            execution_id,
                            transaction_ids[previous_start:previous_end],
                            scores,
                            threshold,
                            previous_chunk_id,
                        )
                        if writer_errors:
                            raise RuntimeError(
                                "Falha ao persistir resultados da análise"
                            ) from writer_errors[0]
                        writer_queue.put(writer_item)
                        total_analyzed += len(writer_item.transaction_ids)
                        total_suspicious += int(previous_suspicious.sum())

                    if current_pending is None:
                        # Termina o lote anterior antes de medir o fallback em CPU.
                        pending_opencl = None
                        inference_chunk_started = perf_counter()
                        scores = executor.score_sequential(chunk_features)
                        inference_seconds += perf_counter() - inference_chunk_started
                        writer_item, suspicious = _create_result_writer_item(
                            execution_id,
                            transaction_ids[start:end],
                            scores,
                            threshold,
                            chunk_id,
                        )
                        if writer_errors:
                            raise RuntimeError(
                                "Falha ao persistir resultados da análise"
                            ) from writer_errors[0]
                        writer_queue.put(writer_item)
                        total_analyzed += len(writer_item.transaction_ids)
                        total_suspicious += int(suspicious.sum())
                    else:
                        pending_opencl = (current_pending, start, end, chunk_id)

                current.total_analisadas = total_analyzed
                current.total_suspeitas = total_suspicious
                db.commit()

            if (
                execution.modo_execucao == ModoExecucao.PARALELO
                and pending_opencl is not None
            ):
                previous_pending, previous_start, previous_end, previous_chunk_id = (
                    pending_opencl
                )
                current = (
                    db.query(ExecucaoAnaliseModel)
                    .filter_by(id_execucao=execution_id)
                    .populate_existing()
                    .first()
                )
                if current is not None and current.status != StatusExecucao.CANCELADA:
                    scores = executor.collect_opencl(previous_pending)
                    inference_seconds += (
                        executor.last_kernel_seconds + executor.last_transfer_seconds
                    )
                    writer_item, previous_suspicious = _create_result_writer_item(
                        execution_id,
                        transaction_ids[previous_start:previous_end],
                        scores,
                        threshold,
                        previous_chunk_id,
                    )
                    if writer_errors:
                        raise RuntimeError(
                            "Falha ao persistir resultados da análise"
                        ) from writer_errors[0]
                    writer_queue.put(writer_item)
                    total_analyzed += len(writer_item.transaction_ids)
                    total_suspicious += int(previous_suspicious.sum())
                    current.total_analisadas = total_analyzed
                    current.total_suspeitas = total_suspicious
                    db.commit()
            logger.info(
                "Análise %s: fase de inferência com %.1f%% de CPU no processo (%s CPUs disponíveis)",
                execution_id,
                sampler.cpu_percent_since(scoring_started, scoring_cpu_started),
                sampler.cpu_capacity,
            )
            _execution_stages[execution_id] = EtapaExecucao.GRAVACAO
            drain_started = perf_counter()
            if writer_queue is not None:
                for _ in writer_threads:
                    writer_queue.put(_WRITER_STOP)
                for writer_thread in writer_threads:
                    writer_thread.join()
            if writer_errors:
                raise RuntimeError(
                    "Falha ao persistir resultados da análise"
                ) from writer_errors[0]
            logger.info(
                "Análise %s: espera pela gravação final em %.3fs",
                execution_id,
                perf_counter() - drain_started,
            )

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
        if writer_queue is not None and writer_threads:
            try:
                for _ in writer_threads:
                    writer_queue.put(_WRITER_STOP)
                for writer_thread in writer_threads:
                    writer_thread.join(timeout=5)
            except Exception:
                logger.exception(
                    "Falha ao encerrar a thread de escrita da análise %s", execution_id
                )
        db.rollback()
        logger.exception("Falha ao executar análise %s", execution_id)
        current = (
            db.query(ExecucaoAnaliseModel)
            .filter_by(id_execucao=execution_id)
            .populate_existing()
            .with_for_update()
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
    finally:
        _execution_stages.pop(execution_id, None)


def _transactions_frame(
    rows: list[Any],
    *,
    measure_columns: tuple[str | int, str | int] = ("Time", "Amount"),
) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(
        [dict(row.atributos or {}) for row in rows],
        coerce_float=True,
    )
    row_count = len(rows)
    frame[measure_columns[0]] = np.fromiter(
        (row.tempo_relativo for row in rows),
        dtype=np.float64,
        count=row_count,
    )
    frame[measure_columns[1]] = np.fromiter(
        (row.valor for row in rows),
        dtype=np.float64,
        count=row_count,
    )
    return frame.replace([np.inf, -np.inf], np.nan)


def _create_executor(
    parameters: dict[str, Any],
    *,
    opencl_device_type: OpenCLDeviceType | None = None,
    training_jobs: int = 1,
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
        training_jobs=training_jobs,
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
        .with_for_update()
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
    metric.nucleos_disponiveis = sampler.cpu_capacity
