from decimal import Decimal
from typing import Any

class Transacao:
    """Entidade de domínio independente da persistência e da camada HTTP."""
    def __init__(self, id_transacao: int | None, id_dataset: int, indice_origem: int, valor: Decimal | None, tempo_relativo: Decimal | None, atributos: dict[str, Any], rotulo_real: bool | None):
        self.id_transacao = id_transacao
        self.id_dataset = id_dataset
        self.indice_origem = indice_origem
        self.valor = valor
        self.tempo_relativo = tempo_relativo
        self.atributos = atributos
        self.rotulo_real = rotulo_real