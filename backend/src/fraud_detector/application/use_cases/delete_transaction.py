from src.fraud_detector.infrastructure.repositories.transaction_repository import TransactionRepository

class DeleteTransactionUseCase:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository

    def execute(self, id_transacao: int) -> None:
        deleted = self.transaction_repository.delete(id_transacao)
        if not deleted:
            raise ValueError("Transação não encontrada")