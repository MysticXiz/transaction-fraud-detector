from sqlalchemy.orm import Session
from src.fraud_detector.domain.entities.transaction import Transacao
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel

class TransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, transaction: Transacao) -> Transacao:
        model = TransacaoModel(id_dataset=transaction.id_dataset, indice_origem=transaction.indice_origem, valor=transaction.valor, tempo_relativo=transaction.tempo_relativo, atributos=transaction.atributos, rotulo_real=transaction.rotulo_real)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._to_entity(model)

    def get_by_id(self, id_transacao: int) -> Transacao | None:
        model = self.db.query(TransacaoModel).filter(TransacaoModel.id_transacao == id_transacao).first()
        return self._to_entity(model) if model else None

    def get_all(self) -> list[Transacao]:
        models = self.db.query(TransacaoModel).all()
        return [self._to_entity(model) for model in models]

    def update(self, id_transacao: int, updates: dict) -> Transacao | None:
        model = self.db.query(TransacaoModel).filter(TransacaoModel.id_transacao == id_transacao).first()
        if model is None:
            return None
        for field, value in updates.items():
            setattr(model, field, value)
        self.db.commit()
        self.db.refresh(model)
        return self._to_entity(model)

    def delete(self, id_transacao: int) -> bool:
        model = self.db.query(TransacaoModel).filter(TransacaoModel.id_transacao == id_transacao).first()
        if model is None:
            return False
        self.db.delete(model)
        self.db.commit()
        return True

    def _to_entity(self, model: TransacaoModel) -> Transacao:
        return Transacao(id_transacao=model.id_transacao, id_dataset=model.id_dataset, indice_origem=model.indice_origem, valor=model.valor, tempo_relativo=model.tempo_relativo, atributos=model.atributos, rotulo_real=model.rotulo_real)