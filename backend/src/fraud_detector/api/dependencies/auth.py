from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.security.jwt import settings


security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Valida o bearer token e retorna apenas usuários existentes e ativos."""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")

    # A existência do token não basta: a conta pode ter sido removida ou desativada.
    user = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == int(user_id)).first()

    if user is None or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado ou inativo")

    return user