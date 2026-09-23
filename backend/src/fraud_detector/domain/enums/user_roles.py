from enum import Enum

class PapelUsuario(str, Enum):
    """Perfis usados pela autorização da API."""
    ADMIN = "ADMIN"
    ANALISTA = "ANALISTA"
    VISUALIZADOR = "VISUALIZADOR"