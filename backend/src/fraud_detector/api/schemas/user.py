from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterSchema(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(..., min_length=8, max_length=255)


class UserLoginSchema(BaseModel):
    email: EmailStr
    senha: str

class UserUpdateSchema(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=120)
    email: EmailStr | None = None
    senha: str | None = Field(None, min_length=8, max_length=255)

class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    nome: str
    email: EmailStr
    papel: str
    ativo: bool
    criado_em: datetime

class TokenSchema(BaseModel):
    access_token: str
    token_type: str