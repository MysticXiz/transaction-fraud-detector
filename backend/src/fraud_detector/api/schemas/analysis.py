from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao


class CriarExecucaoSchema(BaseModel):
    id_dataset: int = Field(gt=0)
    id_modelo: int = Field(gt=0)
    modo_execucao: ModoExecucao
    num_workers: int = Field(ge=1, le=128)
    tamanho_chunk: int | None = Field(default=None, gt=0)
    limiar_decisao: Decimal | None = Field(default=None, ge=0, le=1)


class ExecucaoRespostaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_execucao: int
    id_dataset: int
    id_modelo: int
    dataset_nome: str | None = None
    modelo_nome: str | None = None
    modo_execucao: ModoExecucao
    num_workers: int
    tamanho_chunk: int | None = None
    limiar_aplicado: Decimal
    status: StatusExecucao
    progresso_percentual: int = 0
    iniciada_em: datetime | None = None
    finalizada_em: datetime | None = None
    tempo_total_s: Decimal | None = None
    total_analisadas: int
    total_suspeitas: int
    mensagem_erro: str | None = None
    criado_em: datetime


class MetricaRespostaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tempo_leitura_s: Decimal | None = None
    tempo_preproc_s: Decimal | None = None
    tempo_inferencia_s: Decimal | None = None
    tempo_overhead_s: Decimal | None = None
    cpu_percent_medio: Decimal | None = None
    memoria_pico_mb: Decimal | None = None
    throughput_tps: Decimal | None = None
    nucleos_disponiveis: int | None = None


class ResultadoRespostaSchema(BaseModel):
    id_resultado: int
    id_execucao: int
    id_transacao: int
    score_anomalia: Decimal
    is_suspeita: bool
    limiar_aplicado: Decimal
    chunk_id: int | None = None
    valor: Decimal | None = None


class ResultadosPaginaSchema(BaseModel):
    execucao: ExecucaoRespostaSchema
    metrica: MetricaRespostaSchema
    itens: list[ResultadoRespostaSchema]
    total: int
    pagina: int
    tamanho_pagina: int


class TransacaoDetalheSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_transacao: int
    indice_origem: int
    valor: Decimal | None
    tempo_relativo: Decimal | None
    atributos: dict[str, Any]
    rotulo_real: bool | None


class AvaliacaoHistoricoSchema(BaseModel):
    id_execucao: int
    modo_execucao: ModoExecucao
    num_workers: int
    score_calculado: Decimal
    equivalente_ao_baseline: bool | None


class ResultadoAtualSchema(BaseModel):
    id_execucao: int
    score_anomalia: Decimal
    limiar_aplicado: Decimal
    is_suspeita: bool


class DetalheResultadoSchema(BaseModel):
    transacao: TransacaoDetalheSchema
    resultado_atual: ResultadoAtualSchema
    historico: list[AvaliacaoHistoricoSchema]


class ModeloRespostaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_modelo: int
    nome: str
    algoritmo: str
    versao: str
    limiar_padrao: Decimal
    treinado_em: datetime | None = None
