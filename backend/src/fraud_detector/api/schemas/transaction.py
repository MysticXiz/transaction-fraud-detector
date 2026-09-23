from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class TransacaoCriacaoSchema(BaseModel):
    """Dados aceitos para inserir uma transação."""
    id_dataset: int
    indice_origem: int = Field(..., ge=0)
    valor: Decimal | None = None
    tempo_relativo: Decimal | None = None
    atributos: dict[str, Any] = Field(default_factory=dict)
    rotulo_real: bool | None = None

class TransacaoAtualizacaoSchema(BaseModel):
    """Campos opcionais permitidos em uma atualização parcial."""
    valor: Decimal | None = None
    tempo_relativo: Decimal | None = None
    atributos: dict[str, Any] | None = None
    rotulo_real: bool | None = None

class TransacaoRespostaSchema(BaseModel):
    """Formato público da transação retornada pela API."""
    model_config = ConfigDict(from_attributes=True)
    id_transacao: int
    id_dataset: int
    indice_origem: int
    valor: Decimal | None
    tempo_relativo: Decimal | None
    atributos: dict[str, Any]
    rotulo_real: bool | None