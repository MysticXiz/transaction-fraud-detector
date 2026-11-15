from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.fraud_detector.domain.enums.algorithm_type import TipoAlgoritmo
from src.fraud_detector.infrastructure.database.database import Base


class ModeloDeteccaoModel(Base):
    __tablename__ = "modelo_deteccao"
    __table_args__ = (
        UniqueConstraint("nome", "versao", name="uk_modelo_nome_versao"),
        CheckConstraint("limiar_padrao BETWEEN 0 AND 1", name="ck_modelo_limiar"),
    )

    id_modelo: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    algoritmo: Mapped[TipoAlgoritmo] = mapped_column(
        ENUM(TipoAlgoritmo, name="tipo_algoritmo", create_type=False), nullable=False
    )
    versao: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    hiperparametros: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    caminho_artefato: Mapped[str | None] = mapped_column(String(500))
    limiar_padrao: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0.5000")
    )
    metricas_treino: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    treinado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
