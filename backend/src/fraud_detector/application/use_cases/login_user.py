from fastapi import HTTPException, status
from src.fraud_detector.infrastructure.repositories.user_repository import UserRepository
from src.fraud_detector.infrastructure.security.jwt import create_access_token
from src.fraud_detector.infrastructure.security.password import verify_password
from src.fraud_detector.api.schemas.user import TokenSchema, UserLoginSchema

class LoginUserUseCase:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(self, user_data: UserLoginSchema) -> TokenSchema:
        email = str(user_data.email).lower()
        senha = user_data.senha

        user = self.user_repository.get_by_email(email)
        if not user or not verify_password(senha, user.senha_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
        
        access_token = create_access_token(data={"sub": str(user.id_usuario), "role": user.papel.value})
        return TokenSchema(access_token=access_token, token_type="bearer")