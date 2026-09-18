from datetime import datetime
from src.fraud_detector.domain.enums.user_roles import PapelUsuario

class Usuario:
    def __init__(self, id_usuario: int | None, nome: str, email: str, senha_hash: str, papel: PapelUsuario, ativo: bool, criado_em: datetime | None):
        self.id_usuario = id_usuario
        self.nome = nome
        self.email = email
        self.senha_hash = senha_hash
        self.papel = papel
        self.ativo = ativo
        self.criado_em = criado_em