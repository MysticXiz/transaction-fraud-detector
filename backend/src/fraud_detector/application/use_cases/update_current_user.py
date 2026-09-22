from src.fraud_detector.api.schemas.user import UsuarioAtualizacaoSchema
from src.fraud_detector.domain.entities.user import Usuario
from src.fraud_detector.infrastructure.repositories.user_repository import RepositorioUsuario
from src.fraud_detector.infrastructure.security.password import hash_password

class AtualizarUsuarioAtualUseCase:
    def __init__(self, user_repository: RepositorioUsuario):
        self.user_repository = user_repository

    def execute(self, user: Usuario, user_data: UsuarioAtualizacaoSchema) -> Usuario:
        updates = user_data.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("Nenhum campo foi informado para atualização")
        if "email" in updates:
            updates["email"] = str(updates["email"]).lower()
        if "senha" in updates:
            updates["senha_hash"] = hash_password(updates.pop("senha"))
        updated_user = self.user_repository.update(user.id_usuario, updates)
        if updated_user is None:
            raise ValueError("Usuário não encontrado")
        return updated_user