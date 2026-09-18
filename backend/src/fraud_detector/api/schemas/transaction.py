from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class TransactionCreateSchema(BaseModel):
    id_dataset: int
    indice_origem: int = Field(..., ge=0)
    valor: Decimal | None = None
    tempo_relativo: Decimal | None = None
    atributos: dict[str, Any] = Field(default_factory=dict)
    rotulo_real: bool | None = None

class TransactionUpdateSchema(BaseModel):
    valor: Decimal | None = None
    tempo_relativo: Decimal | None = None
    atributos: dict[str, Any] | None = None
    rotulo_real: bool | None = None

class TransactionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_transacao: int
    id_dataset: int
    indice_origem: int
    valor: Decimal | None
    tempo_relativo: Decimal | None
    atributos: dict[str, Any]
    rotulo_real: bool | None