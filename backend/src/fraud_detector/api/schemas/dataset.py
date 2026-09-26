from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DatasetRespostaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_dataset: int
    nome: str
    descricao: str | None
    hash_arquivo: str
    total_registros: int
    total_colunas: int
    origem: str | None
    possui_rotulo: bool
    importado_em: datetime


class TransacaoAmostraDatasetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    indice_origem: int
    valor: Decimal | None
    tempo_relativo: Decimal | None
    atributos: dict[str, float]
    rotulo_real: bool | None


class DatasetDetalheSchema(DatasetRespostaSchema):
    amostra: list[TransacaoAmostraDatasetSchema]