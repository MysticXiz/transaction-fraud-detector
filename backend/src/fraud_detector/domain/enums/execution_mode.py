from enum import Enum

class ModoExecucao(str, Enum):
    SEQUENCIAL = "SEQUENCIAL"
    PARALELO = "PARALELO"