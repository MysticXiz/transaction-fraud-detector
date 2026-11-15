import logging

from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from src.fraud_detector.config.bootstrap_admin import (
    BOOTSTRAP_ADMIN_EMAIL,
    BOOTSTRAP_ADMIN_NAME,
    BOOTSTRAP_ADMIN_PASSWORD,
    BOOTSTRAP_ADMIN_ROLE,
)
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.security.password import hash_password

logger = logging.getLogger(__name__)


def seed_bootstrap_admin(db: Session) -> bool:
    """Cria o administrador padrão somente quando não há usuários cadastrados."""
    if not inspect(db.bind).has_table(UsuarioModel.__tablename__):
        return False

    user_count = db.query(func.count(UsuarioModel.id_usuario)).scalar() or 0
    if user_count > 0:
        return False

    admin = UsuarioModel(
        nome=BOOTSTRAP_ADMIN_NAME,
        email=BOOTSTRAP_ADMIN_EMAIL,
        senha_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
        papel=BOOTSTRAP_ADMIN_ROLE,
        ativo=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Administrador inicial criado")
    return True
