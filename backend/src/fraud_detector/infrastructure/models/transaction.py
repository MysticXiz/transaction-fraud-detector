from decimal import Decimal
from typing import Any
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.fraud_detector.infrastructure.database.database import Base

class TransacaoModel(Base):
    """Mapeamento SQLAlchemy da tabela de transações persistidas."""
    __tablename__ = "transacao"

    id_transacao: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    id_dataset: Mapped[int] = mapped_column(Integer, ForeignKey("dataset.id_dataset", ondelete="CASCADE"), nullable=False)

    indice_origem: Mapped[int] = mapped_column(Integer, nullable=False)

    valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    tempo_relativo: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    atributos: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    rotulo_real: Mapped[bool | None] = mapped_column(Boolean, nullable=True)