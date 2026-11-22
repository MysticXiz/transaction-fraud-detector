import logging

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from src.fraud_detector.config.settings import settings
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.security.password import (
    LEGACY_ADMIN_EMAIL,
    LEGACY_ADMIN_PASSWORD,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


def seed_bootstrap_admin(db: Session) -> bool:
    """Cria o administrador configurado somente em um banco sem usuários."""
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if email is None and password is None:
        return False
    if not email or not password:
        raise ValueError(
            "Configure BOOTSTRAP_ADMIN_EMAIL e BOOTSTRAP_ADMIN_PASSWORD juntos"
        )
    connection = db.connection()
    if not inspect(connection).has_table(UsuarioModel.__tablename__):
        return False
    if connection.dialect.name == "postgresql":
        db.execute(text("LOCK TABLE usuario IN SHARE ROW EXCLUSIVE MODE"))
    email = email.lower()
    legacy = db.query(UsuarioModel).filter_by(email=LEGACY_ADMIN_EMAIL).first()
    if (
        legacy is not None
        and legacy.papel == PapelUsuario.ADMIN
        and verify_password(LEGACY_ADMIN_PASSWORD, legacy.senha_hash)
    ):
        if (
            email != legacy.email
            and db.query(UsuarioModel).filter_by(email=email).first() is not None
        ):
            raise ValueError("O e-mail do bootstrap pertence a outro usuário")
        legacy.email = email
        legacy.senha_hash = hash_password(password)
        db.commit()
        logger.info("Credenciais do administrador inicial atualizadas")
        return True
    if db.query(UsuarioModel.id_usuario).first() is not None:
        return False

    admin = UsuarioModel(
        nome="Administrador",
        email=email,
        senha_hash=hash_password(password),
        papel=PapelUsuario.ADMIN,
        ativo=True,
    )
    db.add(admin)
    db.commit()
    logger.info("Administrador inicial criado")
    return True
