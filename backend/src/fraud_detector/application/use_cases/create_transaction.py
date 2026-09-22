from src.fraud_detector.api.schemas.transaction import TransacaoCriacaoSchema
from src.fraud_detector.domain.entities.transaction import Transacao
from src.fraud_detector.infrastructure.repositories.transaction_repository import RepositorioTransacao
from sqlalchemy.exc import IntegrityError

class CriarTransacaoUseCase:
    def __init__(self, transaction_repository: RepositorioTransacao):
        self.transaction_repository = transaction_repository

    def execute(self, transaction_data: TransacaoCriacaoSchema) -> Transacao:
        transaction = Transacao(id_transacao=None, id_dataset=transaction_data.id_dataset, indice_origem=transaction_data.indice_origem, valor=transaction_data.valor,  tempo_relativo=transaction_data.tempo_relativo, atributos=transaction_data.atributos, rotulo_real=transaction_data.rotulo_real)
        try:
            return self.transaction_repository.create(transaction)
        except IntegrityError as error:
            self.transaction_repository.db.rollback()
            if "uk_transacao_origem" in str(error.orig):
                raise ValueError("Já existe uma transação com este índice de origem neste dataset")
            raise