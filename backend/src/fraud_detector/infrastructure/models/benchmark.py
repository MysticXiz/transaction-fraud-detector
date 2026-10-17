from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.fraud_detector.domain.enums.benchmark_role import PapelBenchmark
from src.fraud_detector.infrastructure.database.database import Base


class BenchmarkModel(Base):
    __tablename__ = "benchmark"

    id_benchmark: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuario.id_usuario", ondelete="RESTRICT"), nullable=False
    )
    id_dataset: Mapped[int] = mapped_column(
        Integer, ForeignKey("dataset.id_dataset", ondelete="CASCADE"), nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BenchmarkExecucaoModel(Base):
    __tablename__ = "benchmark_execucao"
    __table_args__ = (
        UniqueConstraint("id_benchmark", "id_execucao", name="uk_bexec"),
        CheckConstraint("speedup IS NULL OR speedup > 0", name="ck_bexec_speedup"),
        CheckConstraint(
            "eficiencia IS NULL OR eficiencia > 0", name="ck_bexec_eficien"
        ),
    )

    id_benchmark_exec: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_benchmark: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("benchmark.id_benchmark", ondelete="CASCADE"),
        nullable=False,
    )
    id_execucao: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("execucao_analise.id_execucao", ondelete="CASCADE"),
        nullable=False,
    )
    papel: Mapped[PapelBenchmark] = mapped_column(
        ENUM(PapelBenchmark, name="papel_benchmark", create_type=False),
        nullable=False,
    )
    speedup: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    eficiencia: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
