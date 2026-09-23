from datetime import datetime, timedelta, timezone

from jose import jwt

from src.fraud_detector.config.settings import settings


def create_access_token(data: dict) -> str:
    """Cria um token assinado com expiração definida na configuração do ambiente."""
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire})

    return jwt.encode( to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm,)