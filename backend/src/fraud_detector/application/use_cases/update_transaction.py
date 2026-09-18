from src.fraud_detector.api.schemas.transaction import TransactionUpdateSchema
from src.fraud_detector.infrastructure.repositories.transaction_repository import TransactionRepository

class UpdateTransactionUseCase:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository

    def execute(self, id_transacao: int, transaction_data: TransactionUpdateSchema):
        updates = transaction_data.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("Nenhum campo foi informado para atualização")
        transaction = self.transaction_repository.update(id_transacao, updates)
        if transaction is None:
            raise ValueError("Transação não encontrada")
        return transaction