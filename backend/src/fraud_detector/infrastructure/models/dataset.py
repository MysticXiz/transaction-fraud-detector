from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from src.fraud_detector.infrastructure.database.database import Base

class DatasetModel(Base):
    __tablename__ = "dataset"

    id_dataset: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id_usuario", ondelete="RESTRICT"), nullable=False)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    caminho_arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    hash_arquivo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_colunas: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    origem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    possui_rotulo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    importado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())