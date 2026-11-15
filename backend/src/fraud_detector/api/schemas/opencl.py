from typing import Literal

from pydantic import BaseModel, Field


class OpenCLDeviceSchema(BaseModel):
    tipo: Literal["CPU", "GPU"]
    plataforma: str
    nome: str
    max_work_group_size: int = Field(ge=1)
    work_group_recomendado: int | None = Field(default=None, ge=1)
    chunk_recomendado: int | None = Field(default=None, ge=1)
    preferred_work_group_multiple: int | None = Field(default=None, ge=1)
    unidades_computacao: int | None = Field(default=None, ge=1)
    local_mem_size: int | None = Field(default=None, ge=0)


class OpenCLCapabilitiesSchema(BaseModel):
    dispositivos: list[OpenCLDeviceSchema]


class CalibrarOpenCLSchema(BaseModel):
    tipo_dispositivo: Literal["CPU", "GPU"] = "CPU"
    tamanho_amostra: int = Field(default=20_000, ge=2_000, le=100_000)
    tempo_maximo_s: float = Field(default=5.0, ge=1.0, le=5.0)


class CalibracaoCandidatoSchema(BaseModel):
    work_group_size: int
    tamanho_chunk: int
    throughput_tps: float
    tempo_s: float


class CalibracaoOpenCLRespostaSchema(BaseModel):
    tipo_dispositivo: Literal["CPU", "GPU"]
    work_group_size_recomendado: int
    tamanho_chunk_recomendado: int
    candidatos: list[CalibracaoCandidatoSchema]
    explicacao: str
