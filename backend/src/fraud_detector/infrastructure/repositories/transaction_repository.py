from contextlib import contextmanager

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from src.fraud_detector.infrastructure.models.benchmark import BenchmarkModel
from src.fraud_detector.infrastructure.models.execution import ExecucaoAnaliseModel
from src.fraud_detector.domain.entities.transaction import Transacao
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.models.transaction import TransacaoModel


class DatasetTransactionConflictError(Exception):
    """O dataset ainda é referenciado por uma execução ou benchmark."""


def owned_dataset_for_update(db: Session, owner_id: int) -> Query[DatasetModel]:
    # O lock deve ser adquirido antes de consultar o histórico ou usar o total.
    return (
        db.query(DatasetModel)
        .filter(DatasetModel.id_usuario == owner_id)
        .populate_existing()
        .with_for_update(of=DatasetModel)
    )


class RepositorioTransacao:
    """Traduz operações entre entidades de domínio e modelos SQLAlchemy."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, transaction: Transacao, owner_id: int) -> Transacao:
        with self._mutation():
            dataset = (
                owned_dataset_for_update(self.db, owner_id)
                .filter(DatasetModel.id_dataset == transaction.id_dataset)
                .first()
            )
            if dataset is None:
                raise ValueError("Dataset não encontrado")
            self._ensure_no_history(dataset.id_dataset)
            model = TransacaoModel(
                id_dataset=transaction.id_dataset,
                indice_origem=transaction.indice_origem,
                valor=transaction.valor,
                tempo_relativo=transaction.tempo_relativo,
                atributos=transaction.atributos,
                rotulo_real=transaction.rotulo_real,
            )
            self.db.add(model)
            self._sync_count(dataset)
            self.db.refresh(model)
            return self._to_entity(model)

    def get_by_id(self, id_transacao: int, owner_id: int) -> Transacao | None:
        model = (
            self.db.query(TransacaoModel)
            .join(DatasetModel, DatasetModel.id_dataset == TransacaoModel.id_dataset)
            .filter(
                TransacaoModel.id_transacao == id_transacao,
                DatasetModel.id_usuario == owner_id,
            )
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self, owner_id: int) -> list[Transacao]:
        models = (
            self.db.query(TransacaoModel)
            .join(DatasetModel, DatasetModel.id_dataset == TransacaoModel.id_dataset)
            .filter(DatasetModel.id_usuario == owner_id)
            .all()
        )
        return [self._to_entity(model) for model in models]

    def update(
        self, id_transacao: int, owner_id: int, updates: dict
    ) -> Transacao | None:
        with self._mutation():
            dataset, model = self._find_under_lock(id_transacao, owner_id)
            if dataset is None or model is None:
                return None
            self._ensure_no_history(dataset.id_dataset)
            for field, value in updates.items():
                setattr(model, field, value)
            self._sync_count(dataset)
            self.db.refresh(model)
            return self._to_entity(model)

    def delete(self, id_transacao: int, owner_id: int) -> bool:
        with self._mutation():
            dataset, model = self._find_under_lock(id_transacao, owner_id)
            if dataset is None or model is None:
                return False
            self._ensure_no_history(dataset.id_dataset)
            self.db.delete(model)
            self._sync_count(dataset)
            return True

    @contextmanager
    def _mutation(self):
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _find_under_lock(
        self, id_transacao: int, owner_id: int
    ) -> tuple[DatasetModel | None, TransacaoModel | None]:
        dataset = (
            owned_dataset_for_update(self.db, owner_id)
            .join(TransacaoModel, TransacaoModel.id_dataset == DatasetModel.id_dataset)
            .filter(TransacaoModel.id_transacao == id_transacao)
            .first()
        )
        if dataset is None:
            return None, None
        # Releia a transação após o lock: ela pode ter mudado enquanto esperávamos.
        model = (
            self.db.query(TransacaoModel)
            .filter_by(id_transacao=id_transacao, id_dataset=dataset.id_dataset)
            .populate_existing()
            .first()
        )
        return dataset, model

    def _ensure_no_history(self, dataset_id: int) -> None:
        analysis = self.db.query(ExecucaoAnaliseModel).filter_by(id_dataset=dataset_id)
        benchmark = self.db.query(BenchmarkModel).filter_by(id_dataset=dataset_id)
        if self.db.query(analysis.exists() | benchmark.exists()).scalar():
            raise DatasetTransactionConflictError(
                "Não é possível alterar as transações de um dataset vinculado "
                "a análises ou benchmarks"
            )

    def _sync_count(self, dataset: DatasetModel) -> None:
        # Reconta em vez de incrementar um total que pode estar incorreto.
        self.db.flush()
        dataset.total_registros = (
            self.db.query(func.count())
            .select_from(TransacaoModel)
            .filter_by(id_dataset=dataset.id_dataset)
            .scalar()
        )

    def _to_entity(self, model: TransacaoModel) -> Transacao:
        # A API não deve depender diretamente da representação persistida.
        return Transacao(
            id_transacao=model.id_transacao,
            id_dataset=model.id_dataset,
            indice_origem=model.indice_origem,
            valor=model.valor,
            tempo_relativo=model.tempo_relativo,
            atributos=model.atributos,
            rotulo_real=model.rotulo_real,
        )
