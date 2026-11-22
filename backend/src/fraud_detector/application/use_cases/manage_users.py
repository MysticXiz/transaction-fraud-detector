from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.fraud_detector.api.schemas.user import UsuarioAdministracaoSchema
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.repositories.user_repository import (
    RepositorioUsuario,
)


class GerenciarUsuariosUseCase:
    def __init__(self, repository: RepositorioUsuario):
        self.repository = repository

    def _target(self, actor_id: int, target_id: int) -> UsuarioModel:
        self.repository.lock_account_changes()
        actor = self.repository.get_by_id(actor_id)
        if actor is None or not actor.ativo or actor.papel != PapelUsuario.ADMIN:
            raise HTTPException(status_code=403, detail="Acesso administrativo exigido")
        if actor_id == target_id:
            raise HTTPException(
                status_code=400,
                detail="Este painel só permite gerenciar as contas de outros usuários",
            )
        target = self.repository.get_by_id(target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        return target

    def update(
        self, actor_id: int, target_id: int, changes: UsuarioAdministracaoSchema
    ) -> UsuarioModel:
        target = self._target(actor_id, target_id)
        return self.repository.update_user(target, changes.model_dump())

    def delete(self, actor_id: int, target_id: int) -> None:
        target = self._target(actor_id, target_id)
        try:
            self.repository.delete(target)
        except IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="A conta possui registros vinculados. Você pode desativá-la.",
            ) from error
