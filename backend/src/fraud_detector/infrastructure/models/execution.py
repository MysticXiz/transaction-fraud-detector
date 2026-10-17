from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.fraud_detector.domain.enums.execution_mode import ModoExecucao
from src.fraud_detector.domain.enums.execution_status import StatusExecucao
from src.fraud_detector.infrastructure.database.database import Base


class ExecucaoAnaliseModel(Base):
    __tablename__ = "execucao_analise"
    __table_args__ = (
        CheckConstraint("num_workers BETWEEN 1 AND 128", name="ck_execucao_workers"),
        CheckConstraint(
            "tamanho_chunk IS NULL OR tamanho_chunk > 0", name="ck_execucao_chunk"
        ),
        CheckConstraint(
            "finalizada_em IS NULL OR iniciada_em IS NULL OR finalizada_em >= iniciada_em",
            name="ck_execucao_tempos",
        ),
        CheckConstraint(
            "total_suspeitas <= total_analisadas", name="ck_execucao_totais"
        ),
        CheckConstraint(
            "modo_execucao <> 'SEQUENCIAL' OR num_workers = 1",
            name="ck_execucao_modo_workers",
        ),
    )

    id_execucao: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_dataset: Mapped[int] = mapped_column(
        Integer, ForeignKey("dataset.id_dataset", ondelete="RESTRICT"), nullable=False
    )
    id_modelo: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("modelo_deteccao.id_modelo", ondelete="RESTRICT"),
        nullable=False,
    )
    id_usuario: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuario.id_usuario", ondelete="RESTRICT"), nullable=False
    )
    modo_execucao: Mapped[ModoExecucao] = mapped_column(
        ENUM(ModoExecucao, name="modo_execucao", create_type=False), nullable=False
    )
    num_workers: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    tamanho_chunk: Mapped[int | None] = mapped_column(Integer)
    limiar_aplicado: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0.5000")
    )
    status: Mapped[StatusExecucao] = mapped_column(
        ENUM(StatusExecucao, name="status_execucao", create_type=False),
        nullable=False,
        default=StatusExecucao.PENDENTE,
    )
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tempo_total_s: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    total_analisadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_suspeitas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mensagem_erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResultadoDeteccaoModel(Base):
    __tablename__ = "resultado_deteccao"
    __table_args__ = (
        UniqueConstraint("id_execucao", "id_transacao", name="uk_resultado_exec_trans"),
        CheckConstraint("chunk_id IS NULL OR chunk_id >= 0", name="ck_resultado_chunk"),
    )

    id_resultado: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_execucao: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("execucao_analise.id_execucao", ondelete="CASCADE"),
        nullable=False,
    )
    id_transacao: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("transacao.id_transacao", ondelete="CASCADE"),
        nullable=False,
    )
    score_anomalia: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    is_suspeita: Mapped[bool] = mapped_column(Boolean, nullable=False)
    limiar_aplicado: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    chunk_id: Mapped[int | None] = mapped_column(Integer)


class MetricaExecucaoModel(Base):
    __tablename__ = "metrica_execucao"
    __table_args__ = (
        CheckConstraint(
            "cpu_percent_medio IS NULL OR cpu_percent_medio BETWEEN 0 AND 100",
            name="ck_metrica_cpu",
        ),
    )

    id_metrica: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_execucao: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("execucao_analise.id_execucao", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    tempo_leitura_s: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    tempo_preproc_s: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    tempo_inferencia_s: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    tempo_overhead_s: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    cpu_percent_medio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    memoria_pico_mb: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    throughput_tps: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    nucleos_disponiveis: Mapped[int | None] = mapped_column(SmallInteger)
