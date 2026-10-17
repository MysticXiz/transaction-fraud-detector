import csv
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.fraud_detector.api.schemas.analysis import CriarExecucaoSchema
from src.fraud_detector.api.schemas.analysis import MetricaRespostaSchema
from src.fraud_detector.api.schemas.benchmark import (
    BenchmarkExecucaoRespostaSchema,
    BenchmarkRespostaSchema,
    CriarBenchmarkSchema,
)
from src.fraud_detector.api.routes import analyses as analysis_routes
from src.fraud_detector.application import analysis_service
from src.fraud_detector.api.routes.benchmarks import _render_benchmark_pdf
from src.fraud_detector.computational.preprocessing.preprocessor import Preprocessor
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.benchmark_role import PapelBenchmark
from src.fraud_detector.infrastructure.database.database import Base
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel
from src.fraud_detector.main import app


def test_transaction_frame_restores_model_features_from_persisted_columns():
    rows = [
        TransacaoModel(
            atributos={"V1": 0.25, "Class": 1},
            tempo_relativo=Decimal("4.5000"),
            valor=Decimal("10.25"),
        ),
        TransacaoModel(
            atributos={"V1": -0.5, "Class": 0},
            tempo_relativo=Decimal("8.0000"),
            valor=Decimal("20.00"),
        ),
    ]

    frame = analysis_service._transactions_frame(rows)

    assert list(frame.columns) == ["V1", "Class", "Time", "Amount"]
    assert frame["V1"].tolist() == [0.25, -0.5]
    assert frame["Time"].tolist() == [4.5, 8.0]
    assert frame["Amount"].tolist() == [10.25, 20.0]
    assert "rotulo_real" not in frame.columns
    processor = Preprocessor()
    processor.fit_transform(frame)
    assert processor.feature_names == ("V1", "Time", "Amount")


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        ({}, {"n_estimators": 200, "contamination": 0.0017, "random_state": 42}),
        (
            {
                "n_estimators": 24,
                "contamination": "auto",
                "random_state": 7,
            },
            {"n_estimators": 24, "contamination": "auto", "random_state": 7},
        ),
    ],
)
def test_executor_uses_supported_model_hyperparameters(
    monkeypatch: pytest.MonkeyPatch,
    parameters: dict[str, object],
    expected: dict[str, object],
):
    captured: dict[str, object] = {}

    class FakeExecutor:
        def __init__(self, **kwargs: object):
            captured.update(kwargs)

    monkeypatch.setattr(analysis_service, "OpenCLIsolationForestExecutor", FakeExecutor)

    analysis_service._create_executor(parameters)

    assert captured == expected


@pytest.mark.parametrize(
    "parameters",
    [
        {"n_estimators": 0},
        {"n_estimators": 2001},
        {"contamination": 0},
        {"contamination": 0.6},
        {"random_state": "42"},
    ],
)
def test_executor_rejects_invalid_model_hyperparameters(
    parameters: dict[str, object],
):
    with pytest.raises(ValueError):
        analysis_service._create_executor(parameters)


def test_analysis_api_request_keeps_frontend_field_names_and_validates_workers():
    request = CriarExecucaoSchema(
        id_dataset=1,
        id_modelo=1,
        modo_execucao=ModoExecucao.PARALELO,
        num_workers=8,
        tamanho_chunk=256,
        limiar_decisao=Decimal("0.35"),
    )

    assert request.model_dump() == {
        "id_dataset": 1,
        "id_modelo": 1,
        "modo_execucao": ModoExecucao.PARALELO,
        "num_workers": 8,
        "tamanho_chunk": 256,
        "limiar_decisao": Decimal("0.35"),
    }
    with pytest.raises(ValueError):
        CriarExecucaoSchema(
            id_dataset=1,
            id_modelo=1,
            modo_execucao=ModoExecucao.PARALELO,
            num_workers=129,
        )


def test_benchmark_api_accepts_frontend_configuration_shape():
    payload = CriarBenchmarkSchema.model_validate(
        {
            "id_dataset": 2,
            "id_modelo": 1,
            "configuracoes": [
                {
                    "modo_execucao": "SEQUENCIAL",
                    "num_workers": 1,
                    "rotulo": "Sequencial (Baseline Obrigatório)",
                },
                {
                    "modo_execucao": "PARALELO",
                    "num_workers": 8,
                    "rotulo": "Paralelo (8 workers)",
                },
            ],
        }
    )

    assert len(payload.configuracoes) == 2
    openapi = app.openapi()
    paths = openapi["paths"]
    assert paths["/analises"]["post"]["responses"]["202"]
    assert "/analises/{execution_id}" in paths
    assert "/analises/{execution_id}/cancelar" in paths
    assert "/analises/{execution_id}/resultados" in paths
    assert "/analises/{execution_id}/resultados/{transaction_id}" in paths
    assert "/analises/{execution_id}/resultados/exportar" in paths
    assert "/benchmarks/{benchmark_id}" in paths
    assert "/benchmarks/{benchmark_id}/exportar" in paths
    assert "/modelos" in paths
    assert {
        "modelo_deteccao",
        "execucao_analise",
        "resultado_deteccao",
        "metrica_execucao",
        "benchmark",
        "benchmark_execucao",
    }.issubset(Base.metadata.tables)


def test_metrics_response_can_be_built_from_persisted_orm_attributes():
    metric = SimpleNamespace(
        tempo_leitura_s=Decimal("0.125000"),
        tempo_preproc_s=Decimal("0.250000"),
        tempo_inferencia_s=Decimal("0.500000"),
        tempo_overhead_s=Decimal("0.050000"),
        cpu_percent_medio=Decimal("10.25"),
        memoria_pico_mb=Decimal("128.50"),
        throughput_tps=Decimal("100.00"),
        nucleos_disponiveis=8,
    )

    response = MetricaRespostaSchema.model_validate(metric)

    assert response.cpu_percent_medio == Decimal("10.25")
    assert response.memoria_pico_mb == Decimal("128.50")


def test_benchmark_export_generates_a_pdf_document():
    benchmark = BenchmarkRespostaSchema(
        id_benchmark=7,
        id_dataset=2,
        dataset_nome="Transações teste",
        total_registros=20,
        descricao="Comparação OpenCL",
        criado_em=datetime.now(UTC),
        status="CONCLUIDO",
        execucoes=[
            BenchmarkExecucaoRespostaSchema(
                id_benchmark_exec=1,
                id_execucao=11,
                papel=PapelBenchmark.BASELINE,
                modo_execucao=ModoExecucao.SEQUENCIAL,
                num_workers=1,
                tempo_s=Decimal("1.25"),
                speedup=Decimal("1"),
                eficiencia=Decimal("1"),
            ),
            BenchmarkExecucaoRespostaSchema(
                id_benchmark_exec=2,
                id_execucao=12,
                papel=PapelBenchmark.COMPARACAO,
                modo_execucao=ModoExecucao.PARALELO,
                num_workers=8,
                tempo_s=Decimal("0.75"),
                speedup=Decimal("1.6667"),
                eficiencia=Decimal("0.2083"),
            ),
        ],
    )

    report = _render_benchmark_pdf(benchmark)

    assert report.startswith(b"%PDF-")


def test_result_exports_stream_json_and_csv_with_transaction_features(
    monkeypatch: pytest.MonkeyPatch,
):
    result = SimpleNamespace(
        id_execucao=4,
        id_transacao=9,
        score_anomalia=Decimal("0.875"),
        is_suspeita=True,
        limiar_aplicado=Decimal("0.5"),
        chunk_id=0,
    )
    transaction = TransacaoModel(
        id_transacao=9,
        indice_origem=8,
        valor=Decimal("33.25"),
        tempo_relativo=Decimal("12.5"),
        atributos={"V1": 0.25},
        rotulo_real=None,
    )

    class Query:
        def join(self, *args):
            _ = args
            return self

        def filter(self, *args):
            _ = args
            return self

        def order_by(self, *args):
            _ = args
            return self

        def yield_per(self, size):
            _ = size
            return iter([(result, transaction)])

    class ExportSession:
        def query(self, *args):
            _ = args
            return Query()

        def close(self):
            pass

    monkeypatch.setattr(analysis_routes, "SessionLocal", ExportSession)

    json_output = json.loads("".join(analysis_routes._stream_json_results(4)))
    csv_output = list(
        csv.DictReader(io.StringIO("".join(analysis_routes._stream_csv_results(4))))
    )

    assert json_output[0]["atributos"] == {"V1": 0.25}
    assert json_output[0]["score_anomalia"] == 0.875
    assert json.loads(csv_output[0]["atributos"]) == {"V1": 0.25}
    assert csv_output[0]["is_suspeita"] == "True"
