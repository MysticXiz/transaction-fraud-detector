from src.fraud_detector.api.schemas.transaction import TransactionCreateSchema
from src.fraud_detector.domain.entities.transaction import Transacao
from src.fraud_detector.infrastructure.repositories.transaction_repository import TransactionRepository
from sqlalchemy.exc import IntegrityError

class CreateTransactionUseCase:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository

    def execute(self, transaction_data: TransactionCreateSchema) -> Transacao:
        transaction = Transacao(id_transacao=None, id_dataset=transaction_data.id_dataset, indice_origem=transaction_data.indice_origem, valor=transaction_data.valor,  tempo_relativo=transaction_data.tempo_relativo, atributos=transaction_data.atributos, rotulo_real=transaction_data.rotulo_real)
        try:
            return self.transaction_repository.create(transaction)
        except IntegrityError as error:
            self.transaction_repository.db.rollback()
            if "uk_transacao_origem" in str(error.orig):
                raise ValueError("Já existe uma transação com este índice de origem neste dataset")
            raise