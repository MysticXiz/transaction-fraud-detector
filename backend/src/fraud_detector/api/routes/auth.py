from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.schemas.user import TokenRespostaSchema, UsuarioLoginSchema, UsuarioCadastroSchema, UsuarioRespostaSchema, UsuarioAtualizacaoSchema
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.repositories.user_repository import RepositorioUsuario
from src.fraud_detector.api.dependencies.roles import require_role
from src.fraud_detector.application.use_cases.register_user import RegistrarUsuarioUseCase
from src.fraud_detector.application.use_cases.login_user import LoginUsuarioUseCase
from src.fraud_detector.application.use_cases.update_current_user import AtualizarUsuarioAtualUseCase

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UsuarioRespostaSchema, status_code=status.HTTP_201_CREATED)
async def register(user_data: UsuarioCadastroSchema, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(require_role(PapelUsuario.ADMIN))) -> UsuarioModel:
    """Permite que administradores criem usuários e retorna somente dados públicos."""
    repository = RepositorioUsuario(db)
    register_use_case = RegistrarUsuarioUseCase(repository)
    return register_use_case.execute(user_data)


@auth_router.post("/login", response_model=TokenRespostaSchema)
async def login(credentials: UsuarioLoginSchema, db: Session = Depends(get_db)) -> TokenRespostaSchema:
    """Autentica o usuário sem exigir token prévio."""
    repository = RepositorioUsuario(db)
    login_use_case = LoginUsuarioUseCase(repository)
    return login_use_case.execute(credentials)


@auth_router.get("/me", response_model=UsuarioRespostaSchema)
async def get_me(current_user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
    return current_user


@auth_router.patch("/me", response_model=UsuarioRespostaSchema)
async def update_me(user_data: UsuarioAtualizacaoSchema, current_user: UsuarioModel = Depends(get_current_user), db: Session = Depends(get_db)) -> UsuarioModel:
    repository = RepositorioUsuario(db)
    update_use_case = AtualizarUsuarioAtualUseCase(repository)
    return update_use_case.execute(current_user, user_data)