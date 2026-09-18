from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.schemas.user import TokenSchema, UserLoginSchema, UserRegisterSchema, UserResponseSchema, UserUpdateSchema
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.repositories.user_repository import ( UserRepository, )
from src.fraud_detector.api.dependencies.roles import require_role
from src.fraud_detector.application.use_cases.register_user import RegisterUserUseCase
from src.fraud_detector.application.use_cases.login_user import LoginUserUseCase
from src.fraud_detector.application.use_cases.update_current_user import UpdateCurrentUserUseCase

auth_router = APIRouter(prefix="/auth", tags=["auth"])



@auth_router.post( "/register", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED, )
async def register( user_data: UserRegisterSchema, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(require_role(PapelUsuario.ADMIN)) ) -> UsuarioModel:

    repository = UserRepository(db)
    register_use_case = RegisterUserUseCase(repository)

    return register_use_case.execute(user_data)


@auth_router.post( "/login", response_model=TokenSchema, )
async def login( credentials: UserLoginSchema, db: Session = Depends(get_db), ) -> TokenSchema:

    repository = UserRepository(db)
    login_use_case = LoginUserUseCase(repository)

    return login_use_case.execute(credentials)


@auth_router.get( "/me", response_model=UserResponseSchema, )
async def get_me( current_user: UsuarioModel = Depends(get_current_user), ) -> UsuarioModel:

    return current_user

@auth_router.patch("/me", response_model=UserResponseSchema)
async def update_me(user_data: UserUpdateSchema, current_user: UsuarioModel = Depends(get_current_user), db: Session = Depends(get_db)) -> UsuarioModel:
    repository = UserRepository(db)
    update_use_case = UpdateCurrentUserUseCase(repository)
    return update_use_case.execute(current_user, user_data)