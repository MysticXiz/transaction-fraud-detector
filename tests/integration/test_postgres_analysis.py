import csv
import io
import os
from decimal import Decimal
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.fraud_detector.application import result_exports
from src.fraud_detector.application.analysis_service import create_execution
from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLIsolationForestExecutor,
)
from src.fraud_detector.config.settings import settings
from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.database.database import SessionLocal
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.detection_model import ModeloDeteccaoModel
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.security.password import hash_password
from src.fraud_detector.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Requer banco PostgreSQL de teste inicializado",
)


def wait_for_result(client, path: str) -> dict:
    deadline = monotonic() + 30
    while True:
        response = client.get(path)
        assert response.status_code == 200
        result = response.json()
        if result["status"] not in {"PENDENTE", "EM_ANDAMENTO"}:
            return result
        assert monotonic() < deadline, result
        sleep(0.1)


def test_backend_queue_results_and_downloads_on_postgres(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(result_exports, "_BATCH_ROWS", 10)
    monkeypatch.setattr(settings, "dataset_storage_path", tmp_path)
    unique_id = uuid4().hex
    email = f"tester-{unique_id}@example.com"
    password = "Senha de integração"
    headers = {"X-Requested-With": "XMLHttpRequest"}
    with SessionLocal() as db:
        owner = UsuarioModel(
            nome="Analista teste",
            email=email,
            senha_hash=hash_password(password),
            papel=PapelUsuario.ANALISTA,
            ativo=True,
        )
        db.add(owner)
        db.flush()
        dataset = DatasetModel(
            id_usuario=owner.id_usuario,
            nome="Teste de exportação",
            caminho_arquivo="integracao.csv",
            hash_arquivo=unique_id * 2,
            total_registros=26,
            total_colunas=3,
        )
        db.add(dataset)
        db.flush()
        dataset_id = dataset.id_dataset
        for index in range(26):
            db.add(
                TransacaoModel(
                    id_dataset=dataset_id,
                    indice_origem=index,
                    tempo_relativo=index,
                    valor=index + 10,
                    atributos={"V1": index},
                )
            )
        model_id = db.scalar(
            select(ModeloDeteccaoModel.id_modelo)
            .where(ModeloDeteccaoModel.algoritmo == TipoAlgoritmo.ISOLATION_FOREST)
            .order_by(ModeloDeteccaoModel.id_modelo)
            .limit(1)
        )
        assert model_id is not None
        interrupted = create_execution(
            db,
            owner_id=owner.id_usuario,
            dataset_id=dataset_id,
            model_id=model_id,
            mode=ModoExecucao.SEQUENCIAL,
            work_group_size=1,
            device_type=None,
            chunk_size=10,
            threshold=None,
            commit=False,
        )
        interrupted_id = interrupted.id_execucao
        interrupted.status = StatusExecucao.EM_ANDAMENTO
        db.commit()

    with TestClient(app) as client:
        credentials = {"email": email, "senha": password}
        assert client.post("/auth/session", json=credentials).status_code == 403
        login = client.post("/auth/session", json=credentials, headers=headers)
        assert login.status_code == 204
        assert "HttpOnly" in login.headers["set-cookie"]
        assert "SameSite=lax" in login.headers["set-cookie"]
        assert client.get("/auth/me").json()["email"] == email

        assert client.get("/health").status_code == 200
        job = client.post(
            "/datasets/importacoes",
            headers=headers,
            json={
                "nome": "Importação CI",
                "origem": "Sintética",
                "nome_arquivo": "ci.csv",
            },
        )
        assert job.status_code == 201
        job_path = f"/datasets/importacoes/{job.json()['id_importacao']}"
        csv_data = bytes([10]).join([b"Time,Amount,V1", b"0,10,1", b"1,20,2", b""])
        csv_file = {"arquivo": ("ci.csv", csv_data, "text/csv")}
        imported = client.post(f"{job_path}/arquivo", files=csv_file, headers=headers)
        assert imported.status_code == 200, imported.text
        state = client.get(job_path).json()
        assert state["status"] == "CONCLUIDO"
        assert state["id_dataset"] == imported.json()["id_dataset"]
        assert imported.json()["total_registros"] == 2
        assert (
            client.post(
                f"{job_path}/arquivo", files=csv_file, headers=headers
            ).status_code
            == 409
        )

        payload = {
            "id_dataset": dataset_id,
            "id_modelo": model_id,
            "modo_execucao": "SEQUENCIAL",
            "tamanho_chunk": 10,
            "limiar_decisao": "0",
        }
        assert client.post("/analises", json=payload).status_code == 403
        created = client.post("/analises", json=payload, headers=headers)
        assert created.status_code == 202
        assert created.json()["status"] == "PENDENTE"
        interrupted_path = f"/analises/{interrupted_id}"
        assert wait_for_result(client, interrupted_path)["status"] == "FALHA"
        assert client.get(f"{interrupted_path}/resultados/exportar").status_code == 409
        analysis_path = f"/analises/{created.json()['id_execucao']}"
        assert wait_for_result(client, analysis_path)["status"] == "CONCLUIDA"
        base = f"{analysis_path}/resultados"

        page = client.get(base, params={"pagina": 2, "is_suspeita": True}).json()
        assert page["execucao"]["status"] == "CONCLUIDA"
        assert page["total"] == 26
        assert len(page["itens"]) == 1
        json_download = client.get(
            f"{base}/exportar", params={"formato": "json", "is_suspeita": True}
        )
        assert json_download.status_code == 200
        rows = json_download.json()
        assert len(rows) == 26
        assert len(json_download.text.splitlines()) == len(rows) + 2
        assert rows[-1]["id_transacao"] == page["itens"][0]["id_transacao"]
        transaction_path = f"/transactions/{rows[-1]['id_transacao']}"
        assert (
            client.patch(
                transaction_path, json={"valor": "1"}, headers=headers
            ).status_code
            == 409
        )
        assert client.delete(transaction_path, headers=headers).status_code == 409
        empty = client.get(
            f"{base}/exportar", params={"formato": "json", "valor_minimo": 100}
        )
        assert empty.json() == []

        download = client.get(f"{base}/exportar", params={"valor_minimo": 35})
        assert download.headers["content-type"].startswith("text/csv")
        assert "attachment" in download.headers["content-disposition"]
        exported = list(csv.DictReader(io.StringIO(download.text)))
        assert len(exported) == 1
        assert exported[0]["valor"] == "35.00"
        unsupported = client.get(f"{base}/exportar", params={"formato": "pdf"})
        assert unsupported.status_code == 422

        submit_opencl = OpenCLIsolationForestExecutor.submit_opencl
        submissions = 0

        def timed_submit(executor, *args, **kwargs):
            nonlocal submissions
            submissions += 1
            sleep(0.02)
            return submit_opencl(executor, *args, **kwargs)

        monkeypatch.setattr(
            OpenCLIsolationForestExecutor, "submit_opencl", timed_submit
        )
        benchmark_payload = {
            "id_dataset": dataset_id,
            "id_modelo": model_id,
            "configuracoes": [
                {"modo_execucao": "SEQUENCIAL", "rotulo": "Baseline"},
                {
                    "modo_execucao": "PARALELO",
                    "rotulo": "OpenCL CPU",
                    "work_group_size": 1,
                    "tipo_dispositivo": "CPU",
                },
            ],
        }
        benchmark = client.post("/benchmarks", json=benchmark_payload, headers=headers)
        assert benchmark.status_code == 202
        report = wait_for_result(
            client, f"/benchmarks/{benchmark.json()['id_benchmark']}"
        )
        assert report["status"] == "CONCLUIDO", report
        assert report["inferencia_sincronizada"] is True
        assert submissions == 2  # Aquecimento e medição.
        baseline, parallel = report["execucoes"]
        parallel_time = Decimal(parallel["tempo_inferencia_s"])
        assert parallel_time >= Decimal("0.02")
        expected_speedup = Decimal(baseline["tempo_inferencia_s"]) / parallel_time
        actual_speedup = Decimal(parallel["speedup"])
        assert abs(actual_speedup - expected_speedup) <= Decimal("0.00005")

        assert client.post("/auth/logout", headers=headers).status_code == 204
        assert client.get(f"{base}/exportar").status_code == 401
