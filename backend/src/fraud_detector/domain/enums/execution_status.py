from enum import Enum

class StatusExecucao(str, Enum):
    """Estados possíveis de uma execução de análise."""
    PENDENTE = "PENDENTE"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    FALHA = "FALHA"
    CANCELADA = "CANCELADA"