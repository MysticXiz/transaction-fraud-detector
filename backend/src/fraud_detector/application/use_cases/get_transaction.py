from src.fraud_detector.domain.entities.transaction import Transacao
from src.fraud_detector.infrastructure.repositories.transaction_repository import (
    RepositorioTransacao,
)


class ObterTransacaoUseCase:
    """Consulta transações através da abstração de repositório."""

    def __init__(self, transaction_repository: RepositorioTransacao):
        self.transaction_repository = transaction_repository

    def get_by_id(self, id_transacao: int, owner_id: int) -> Transacao | None:
        return self.transaction_repository.get_by_id(id_transacao, owner_id)

    def get_all(self, owner_id: int) -> list[Transacao]:
        return self.transaction_repository.get_all(owner_id)
