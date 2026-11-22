from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.fraud_detector.api.dependencies.roles import require_role
from src.fraud_detector.config.settings import MIB, MAX_UPLOAD_LIMIT_MIB
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.upload_settings import (
    get_upload_limit,
    save_upload_limit,
)

admin_only = Depends(require_role(PapelUsuario.ADMIN))
server_settings_router = APIRouter(
    prefix="/admin/configuracoes", tags=["Administração"], dependencies=[admin_only]
)


class UploadLimitUpdate(BaseModel):
    limite_mib: int = Field(strict=True, ge=1, le=MAX_UPLOAD_LIMIT_MIB)


class UploadLimitSettings(BaseModel):
    limite_bytes: int
    maximo_mib: int = MAX_UPLOAD_LIMIT_MIB


@server_settings_router.get("/uploads")
def get_upload_settings() -> UploadLimitSettings:
    return UploadLimitSettings(limite_bytes=get_upload_limit())


@server_settings_router.put("/uploads")
def update_upload_settings(payload: UploadLimitUpdate) -> UploadLimitSettings:
    limit_bytes = payload.limite_mib * MIB
    save_upload_limit(limit_bytes)
    return UploadLimitSettings(limite_bytes=limit_bytes)
