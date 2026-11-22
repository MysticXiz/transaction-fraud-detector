import asyncio

import pytest
from fastapi import FastAPI, UploadFile
from starlette import formparsers
from starlette.responses import StreamingResponse

from src.fraud_detector.api.resource_middleware import UploadBodyLimitMiddleware
from src.fraud_detector.config.settings import MIB, settings
from src.fraud_detector.infrastructure.upload_settings import save_upload_limit


@pytest.fixture
def upload_app():
    app = FastAPI()
    app.add_middleware(UploadBodyLimitMiddleware)

    @app.post("/datasets")
    @app.post("/datasets/importacoes/{import_id}/arquivo")
    async def upload(arquivo: UploadFile):
        return {"size": arquivo.size}

    @app.get("/analises/7/resultados/exportar")
    async def export():
        return StreamingResponse(iter([b"first", b"second"]))

    return app


def _request(app, path, chunks=(), *, method="POST", headers=(), root_path=""):
    pending = iter(enumerate(chunks))
    messages = []
    reads = 0

    async def receive():
        nonlocal reads
        item = next(pending, None)
        if item is None:
            await asyncio.Future()
        index, chunk = item
        reads += 1
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": index + 1 < len(chunks),
        }

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "method": method,
        "path": path,
        "root_path": root_path,
        "headers": list(headers),
        "query_string": b"",
    }
    asyncio.run(asyncio.wait_for(app(scope, receive, send), timeout=5))
    return messages, reads


def _configure_upload_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "dataset_storage_path", tmp_path)
    monkeypatch.setattr(settings, "max_dataset_upload_bytes", 2 * MIB)
    monkeypatch.setattr(settings, "dataset_upload_multipart_overhead_bytes", 16)
    save_upload_limit(MIB)
    return MIB + 16


def _multipart(file_size):
    return (
        b'--boundary\r\nContent-Disposition: form-data; name="arquivo"; '
        b'filename="data.csv"\r\n\r\n',
        b"a" * file_size,
        b"\r\n--boundary--\r\n",
    )


_MULTIPART_HEADER = (b"content-type", b"multipart/form-data; boundary=boundary")


@pytest.mark.parametrize(
    ("path", "root_path"),
    [("/datasets", ""), ("/api/datasets/importacoes/17/arquivo/", "/api")],
)
def test_rejects_declared_size_without_reading_body(
    upload_app, tmp_path, monkeypatch, path, root_path
):
    limit = _configure_upload_limit(tmp_path, monkeypatch)
    messages, reads = _request(
        upload_app,
        path,
        headers=[_MULTIPART_HEADER, (b"content-length", str(limit + 1).encode())],
        root_path=root_path,
    )
    assert reads == 0
    assert messages[0]["status"] == 413
    assert b"Arquivo excede o limite de upload" in messages[1]["body"]


@pytest.mark.parametrize("length", [None, b"12"])
def test_rejects_oversized_stream_and_closes_partial_upload(
    upload_app, tmp_path, monkeypatch, length
):
    limit = _configure_upload_limit(tmp_path, monkeypatch)
    opened = []
    spool = formparsers.SpooledTemporaryFile

    def record_spool(*args, **kwargs):
        file = spool(*args, **{**kwargs, "max_size": 16})
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", record_spool)
    head, data, end = _multipart(limit)
    headers = [_MULTIPART_HEADER]
    if length is not None:
        headers.append((b"content-length", length))
    messages, reads = _request(
        upload_app,
        "/datasets/importacoes/17/arquivo",
        (head + data[:128], data[128:], end),
        headers=headers,
    )
    assert reads == 2
    assert [message["type"] for message in messages] == [
        "http.response.start",
        "http.response.body",
    ]
    assert messages[0]["status"] == 413
    assert len(opened) == 1 and opened[0].closed


def test_accepts_body_at_limit(upload_app, tmp_path, monkeypatch):
    limit = _configure_upload_limit(tmp_path, monkeypatch)
    file_size = limit - sum(map(len, _multipart(0)))
    messages, reads = _request(
        upload_app,
        "/datasets",
        _multipart(file_size),
        headers=[_MULTIPART_HEADER, (b"content-length", str(limit).encode())],
    )
    assert reads == 3
    assert messages[0]["status"] == 200
    assert messages[1]["body"] == f'{{"size":{file_size}}}'.encode()


def test_export_still_streams_without_consulting_upload_limit(upload_app, monkeypatch):
    def unexpected_limit_lookup():
        pytest.fail("Export should not consult the upload limit")

    monkeypatch.setattr(
        "src.fraud_detector.api.resource_middleware.get_upload_limit",
        unexpected_limit_lookup,
    )
    messages, reads = _request(
        upload_app, "/analises/7/resultados/exportar", method="GET"
    )
    assert reads == 0
    assert messages[0]["status"] == 200
    assert [message["body"] for message in messages[1:]] == [b"first", b"second", b""]
