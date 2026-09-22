from enum import Enum

class PapelUsuario(str, Enum):
    ADMIN = "ADMIN"
    ANALISTA = "ANALISTA"
    VISUALIZADOR = "VISUALIZADOR"