import re

from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.fraud_detector.config.settings import settings
from src.fraud_detector.infrastructure.upload_settings import get_upload_limit

_UPLOAD_PATH = re.compile(r"/datasets(?:/importacoes/[^/]+/arquivo)?/?")
_UPLOAD_LIMIT_DETAIL = "Arquivo excede o limite de upload"


class _UploadBodyTooLarge(MultiPartException):
    # Older Starlette versions only close partially spooled files on this type.
    pass


def _is_upload(scope: Scope) -> bool:
    if scope["type"] != "http" or scope["method"] != "POST":
        return False
    path = scope["path"]
    root = scope.get("root_path", "").rstrip("/")
    if root and path.startswith(root + "/"):
        path = path[len(root) :]
    return _UPLOAD_PATH.fullmatch(path) is not None


def _declared_length_exceeds(scope: Scope, limit: int) -> bool:
    maximum = str(limit).encode("ascii")
    for name, value in scope["headers"]:
        if name == b"content-length":
            value = value.strip()
            if value.isdigit():
                digits = value.lstrip(b"0")
                if (len(digits), digits) > (len(maximum), maximum):
                    return True
    return False


class UploadBodyLimitMiddleware:
    """Limit upload bodies before FastAPI parses and spools multipart files."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _is_upload(scope):
            await self.app(scope, receive, send)
            return

        file_limit = await run_in_threadpool(get_upload_limit)
        limit = file_limit + settings.dataset_upload_multipart_overhead_bytes
        too_large = JSONResponse({"detail": _UPLOAD_LIMIT_DETAIL}, status_code=413)
        if _declared_length_exceeds(scope, limit):
            await too_large(scope, receive, send)
            return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _UploadBodyTooLarge(_UPLOAD_LIMIT_DETAIL)
            return message

        async def limited_send(message: Message) -> None:
            nonlocal response_started
            if exceeded and not response_started:
                # FastAPI can turn a parser error into 400. Do not forward that
                # response; send the limit response after the parser unwinds.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except _UploadBodyTooLarge:
            if response_started:
                raise
        if exceeded and not response_started:
            await too_large(scope, receive, send)
