from pydantic import BaseModel, Field


class DatasetImportCreateSchema(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    origem: str = Field(min_length=1, max_length=80)
    descricao: str | None = Field(default=None, max_length=1000)
    nome_arquivo: str = Field(min_length=1, max_length=255)


class DatasetImportJobSchema(BaseModel):
    id_importacao: int
    status: str
    mensagem_erro: str | None
    id_dataset: int | None
