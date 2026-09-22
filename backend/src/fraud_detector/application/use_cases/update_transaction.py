from src.fraud_detector.api.schemas.transaction import TransacaoAtualizacaoSchema
from src.fraud_detector.infrastructure.repositories.transaction_repository import RepositorioTransacao

class AtualizarTransacaoUseCase:
    def __init__(self, transaction_repository: RepositorioTransacao):
        self.transaction_repository = transaction_repository

    def execute(self, id_transacao: int, transaction_data: TransacaoAtualizacaoSchema):
        updates = transaction_data.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("Nenhum campo foi informado para atualização")
        transaction = self.transaction_repository.update(id_transacao, updates)
        if transaction is None:
            raise ValueError("Transação não encontrada")
        return transaction