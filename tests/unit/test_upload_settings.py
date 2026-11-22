from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.routes.server_settings import server_settings_router
from src.fraud_detector.config.settings import MIB, settings
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.upload_settings import get_upload_limit


def test_admin_can_persist_global_upload_limit(tmp_path, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setattr(settings, "dataset_storage_path", tmp_path)
    monkeypatch.setattr(settings, "max_dataset_upload_bytes", 200 * MIB)
    app = FastAPI()
    app.include_router(server_settings_router)
    user = SimpleNamespace(papel=PapelUsuario.ANALISTA)
    app.dependency_overrides[get_current_user] = lambda: user
    url = "/admin/configuracoes/uploads"

    with TestClient(app) as client:
        assert client.get(url).status_code == 403
        assert client.put(url, json={"limite_mib": 25}).status_code == 403
        assert get_upload_limit() == 200 * MIB

        user.papel = PapelUsuario.ADMIN
        assert client.put(url, json={"limite_mib": 0}).status_code == 422
        assert client.put(url, json={"limite_mib": 25}).status_code == 200
        assert client.get(url).json()["limite_bytes"] == 25 * MIB

    monkeypatch.setattr(settings, "max_dataset_upload_bytes", 100 * MIB)
    assert get_upload_limit() == 25 * MIB
