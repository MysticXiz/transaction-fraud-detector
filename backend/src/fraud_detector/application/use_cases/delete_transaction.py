from src.fraud_detector.infrastructure.repositories.transaction_repository import RepositorioTransacao

class ExcluirTransacaoUseCase:
    def __init__(self, transaction_repository: RepositorioTransacao):
        self.transaction_repository = transaction_repository

    def execute(self, id_transacao: int) -> None:
        deleted = self.transaction_repository.delete(id_transacao)
        if not deleted:
            raise ValueError("Transação não encontrada")