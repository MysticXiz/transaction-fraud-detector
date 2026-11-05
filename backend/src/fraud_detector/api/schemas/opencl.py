from typing import Literal

from pydantic import BaseModel, Field


class OpenCLDeviceSchema(BaseModel):
    tipo: Literal["CPU", "GPU"]
    plataforma: str
    nome: str
    max_work_group_size: int = Field(ge=1, le=128)


class OpenCLCapabilitiesSchema(BaseModel):
    dispositivos: list[OpenCLDeviceSchema]
