from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.benchmark_role import PapelBenchmark


class BenchmarkConfiguracaoSchema(BaseModel):
    modo_execucao: ModoExecucao
    num_workers: int = Field(ge=1, le=128)
    rotulo: str = Field(min_length=1, max_length=120)
    tipo_dispositivo: Literal["CPU", "GPU"] | None = None


class CriarBenchmarkSchema(BaseModel):
    id_dataset: int = Field(gt=0)
    id_modelo: int = Field(gt=0)
    configuracoes: list[BenchmarkConfiguracaoSchema] = Field(
        min_length=1, max_length=10
    )


class BenchmarkExecucaoRespostaSchema(BaseModel):
    id_benchmark_exec: int
    id_execucao: int
    papel: PapelBenchmark
    tipo_dispositivo: Literal["CPU", "GPU"] | None = None
    modo_execucao: ModoExecucao
    num_workers: int
    tempo_s: Decimal | None
    speedup: Decimal | None
    eficiencia: Decimal | None


class BenchmarkRespostaSchema(BaseModel):
    id_benchmark: int
    id_dataset: int
    dataset_nome: str
    total_registros: int
    descricao: str | None
    criado_em: datetime
    status: Literal[
        "PENDENTE",
        "EM_ANDAMENTO",
        "CANCELAMENTO_SOLICITADO",
        "CONCLUIDO",
        "FALHA",
        "CANCELADO",
    ]
    mensagem_erro: str | None = None
    execucoes: list[BenchmarkExecucaoRespostaSchema]
