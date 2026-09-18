from src.fraud_detector.domain.entities.transaction import Transacao
from src.fraud_detector.infrastructure.repositories.transaction_repository import TransactionRepository

class GetTransactionUseCase:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository

    def get_by_id(self, id_transacao: int) -> Transacao | None:
        return self.transaction_repository.get_by_id(id_transacao)

    def get_all(self) -> list[Transacao]:
        return self.transaction_repository.get_all()