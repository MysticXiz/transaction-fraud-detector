from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from src.fraud_detector.infrastructure.database.database import Base
from src.fraud_detector.domain.enums.user_roles import PapelUsuario


class UsuarioModel(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column( Integer, primary_key=True, )

    nome: Mapped[str] = mapped_column( String(120), nullable=False, )

    email: Mapped[str] = mapped_column( String(160), unique=True, nullable=False, )

    senha_hash: Mapped[str] = mapped_column( String(255), nullable=False, )

    papel: Mapped[PapelUsuario] = mapped_column(SQLEnum(PapelUsuario, name="papel_usuario", create_type=False), nullable=False, default=PapelUsuario.ANALISTA)

    ativo: Mapped[bool] = mapped_column( Boolean, nullable=False, default=True, )

    criado_em: Mapped[datetime] = mapped_column( DateTime(timezone=True), nullable=False, server_default=func.now(), )
