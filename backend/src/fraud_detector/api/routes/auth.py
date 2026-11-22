from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import (
    SESSION_COOKIE,
    get_current_user,
    require_session_header,
)
from src.fraud_detector.config.settings import settings
from src.fraud_detector.api.schemas.user import (
    TokenRespostaSchema,
    UsuarioLoginSchema,
    UsuarioCadastroSchema,
    UsuarioRespostaSchema,
    UsuarioAtualizacaoSchema,
    UsuarioAdministracaoSchema,
)
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.domain.enums.user_roles import PapelUsuario
from src.fraud_detector.infrastructure.repositories.user_repository import (
    RepositorioUsuario,
)
from src.fraud_detector.api.dependencies.roles import require_role
from src.fraud_detector.api.dependencies.roles import require_write_access
from src.fraud_detector.application.use_cases.register_user import (
    RegistrarUsuarioUseCase,
)
from src.fraud_detector.application.use_cases.login_user import LoginUsuarioUseCase
from src.fraud_detector.application.use_cases.manage_users import (
    GerenciarUsuariosUseCase,
)
from src.fraud_detector.application.use_cases.update_current_user import (
    AtualizarUsuarioAtualUseCase,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/register",
    response_model=UsuarioRespostaSchema,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UsuarioCadastroSchema,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(require_role(PapelUsuario.ADMIN)),
) -> UsuarioModel:
    """Permite que administradores criem usuários e retorna somente dados públicos."""
    repository = RepositorioUsuario(db)
    register_use_case = RegistrarUsuarioUseCase(repository)
    return register_use_case.execute(user_data)


@auth_router.post("/login", response_model=TokenRespostaSchema)
def login(
    credentials: UsuarioLoginSchema, db: Session = Depends(get_db)
) -> TokenRespostaSchema:
    """Autentica o usuário sem exigir token prévio."""
    repository = RepositorioUsuario(db)
    login_use_case = LoginUsuarioUseCase(repository)
    return login_use_case.execute(credentials)


@auth_router.post("/session", status_code=status.HTTP_204_NO_CONTENT)
def create_session(
    credentials: UsuarioLoginSchema,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    require_session_header(request)
    token = login(credentials, db)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.set_cookie(
        SESSION_COOKIE,
        token.access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
    return response


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    require_session_header(request)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
    return response


@auth_router.get("/me", response_model=UsuarioRespostaSchema)
def get_me(
    current_user: UsuarioModel = Depends(get_current_user),
) -> UsuarioModel:
    return current_user


@auth_router.patch("/me", response_model=UsuarioRespostaSchema)
def update_me(
    user_data: UsuarioAtualizacaoSchema,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> UsuarioModel:
    repository = RepositorioUsuario(db)
    update_use_case = AtualizarUsuarioAtualUseCase(repository)
    return update_use_case.execute(current_user, user_data)


@auth_router.get(
    "/users",
    response_model=list[UsuarioRespostaSchema],
    dependencies=[Depends(require_role(PapelUsuario.ADMIN))],
)
def list_users(db: Session = Depends(get_db)) -> list[UsuarioModel]:
    return RepositorioUsuario(db).list_all()


@auth_router.put("/users/{id_usuario}", response_model=UsuarioRespostaSchema)
def update_user(
    id_usuario: int,
    changes: UsuarioAdministracaoSchema,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(require_role(PapelUsuario.ADMIN)),
) -> UsuarioModel:
    use_case = GerenciarUsuariosUseCase(RepositorioUsuario(db))
    return use_case.update(current_user.id_usuario, id_usuario, changes)


@auth_router.delete("/users/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id_usuario: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(require_role(PapelUsuario.ADMIN)),
) -> Response:
    use_case = GerenciarUsuariosUseCase(RepositorioUsuario(db))
    use_case.delete(current_user.id_usuario, id_usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
