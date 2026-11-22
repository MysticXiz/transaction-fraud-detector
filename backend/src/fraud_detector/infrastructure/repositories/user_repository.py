from sqlalchemy import text
from sqlalchemy.orm import Session

from src.fraud_detector.infrastructure.models.user import UsuarioModel


class RepositorioUsuario:
    """Encapsula operações de persistência do usuário para os casos de uso."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> UsuarioModel | None:
        return self.db.query(UsuarioModel).filter(UsuarioModel.email == email).first()

    def list_all(self) -> list[UsuarioModel]:
        return self.db.query(UsuarioModel).order_by(UsuarioModel.id_usuario).all()

    def lock_account_changes(self) -> None:
        if self.db.connection().dialect.name == "postgresql":
            self.db.execute(text("LOCK TABLE usuario IN SHARE ROW EXCLUSIVE MODE"))

    def create(self, user: UsuarioModel) -> UsuarioModel:
        # refresh recupera campos gerados pelo banco, como id e data de criação.
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, id_usuario: int) -> UsuarioModel | None:
        return (
            self.db.query(UsuarioModel)
            .populate_existing()
            .filter(UsuarioModel.id_usuario == id_usuario)
            .first()
        )

    def delete(self, user: UsuarioModel) -> None:
        self.db.delete(user)
        self.db.commit()

    def update(self, id_usuario: int, updates: dict) -> UsuarioModel | None:
        user = self.get_by_id(id_usuario)
        if user is None:
            return None
        return self.update_user(user, updates)

    def update_user(self, user: UsuarioModel, updates: dict) -> UsuarioModel:
        for field, value in updates.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user
