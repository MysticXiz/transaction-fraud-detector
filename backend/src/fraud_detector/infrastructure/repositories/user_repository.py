from sqlalchemy.orm import Session

from src.fraud_detector.infrastructure.models.user import UsuarioModel


class RepositorioUsuario:
    """Encapsula operações de persistência do usuário para os casos de uso."""
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> UsuarioModel | None:
        return self.db.query(UsuarioModel).filter(UsuarioModel.email == email).first()

    def create(self, user: UsuarioModel) -> UsuarioModel:
        # refresh recupera campos gerados pelo banco, como id e data de criação.
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, id_usuario: int, updates: dict) -> UsuarioModel | None:
        user = self.db.query(UsuarioModel).filter(UsuarioModel.id_usuario == id_usuario).first()
        if user is None:
            return None
        for field, value in updates.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user