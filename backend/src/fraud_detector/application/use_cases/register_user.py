from src.fraud_detector.infrastructure.repositories.user_repository import RepositorioUsuario
from src.fraud_detector.infrastructure.models.user import UsuarioModel, PapelUsuario
from src.fraud_detector.infrastructure.security.password import hash_password
from src.fraud_detector.api.schemas.user import UsuarioCadastroSchema
from fastapi import HTTPException, status

class RegistrarUsuarioUseCase:
    """Aplica as regras de cadastro antes de persistir um novo usuário."""
    def __init__(self, repository: RepositorioUsuario):
        self.repository = repository

    def execute(self, user_data: UsuarioCadastroSchema) -> UsuarioModel:
        email = str(user_data.email).lower()
        nome = user_data.nome.strip()
        senha = user_data.senha
        papel = user_data.papel or PapelUsuario.ANALISTA

        # O e-mail normalizado evita duplicidade causada por diferenças de caixa.
        existing_user = self.repository.get_by_email(email)
        if existing_user is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já registrado")

        new_user = UsuarioModel(nome=nome, email=email, senha_hash=hash_password(senha), papel=papel, ativo=True)

        return self.repository.create(new_user)
    