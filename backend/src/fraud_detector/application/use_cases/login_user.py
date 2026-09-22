from fastapi import HTTPException, status
from src.fraud_detector.infrastructure.repositories.user_repository import RepositorioUsuario
from src.fraud_detector.infrastructure.security.jwt import create_access_token
from src.fraud_detector.infrastructure.security.password import verify_password
from src.fraud_detector.api.schemas.user import TokenRespostaSchema, UsuarioLoginSchema

class LoginUsuarioUseCase:
    def __init__(self, user_repository: RepositorioUsuario):
        self.user_repository = user_repository

    def execute(self, user_data: UsuarioLoginSchema) -> TokenRespostaSchema:
        email = str(user_data.email).lower()
        senha = user_data.senha

        user = self.user_repository.get_by_email(email)
        if not user or not verify_password(senha, user.senha_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

        access_token = create_access_token(data={"sub": str(user.id_usuario), "role": user.papel.value})
        return TokenRespostaSchema(access_token=access_token, token_type="bearer")