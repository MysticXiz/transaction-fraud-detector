from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.fraud_detector.infrastructure.database.database import Base


class DatasetImportJobModel(Base):
    __tablename__ = "dataset_import_job"

    id_importacao: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    origem: Mapped[str] = mapped_column(String(80), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDENTE", server_default="PENDENTE"
    )
    cancelamento_solicitado: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    mensagem_erro: Mapped[str | None] = mapped_column(Text)
    id_dataset: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dataset.id_dataset", ondelete="SET NULL")
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
