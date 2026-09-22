from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioCadastroSchema(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(..., min_length=8, max_length=255)


class UsuarioLoginSchema(BaseModel):
    email: EmailStr
    senha: str

class UsuarioAtualizacaoSchema(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=120)
    email: EmailStr | None = None
    senha: str | None = Field(None, min_length=8, max_length=255)

class UsuarioRespostaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    nome: str
    email: EmailStr
    papel: str
    ativo: bool
    criado_em: datetime

class TokenRespostaSchema(BaseModel):
    access_token: str
    token_type: str