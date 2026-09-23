from fastapi import Depends, HTTPException, status
from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.infrastructure.models.user import PapelUsuario, UsuarioModel


def require_role(*allowed_roles: PapelUsuario):
    """Cria uma dependência reutilizável para autorização por perfil."""
    def role_checker(current_user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
        if current_user.papel not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não possui permissão para acessar este recurso")
        return current_user
    return role_checker