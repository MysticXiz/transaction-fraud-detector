from fastapi import Depends
from sqlalchemy.orm import Session
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.repositories.transaction_repository import RepositorioTransacao


def get_transaction_repository(db: Session = Depends(get_db)) -> RepositorioTransacao:
    return RepositorioTransacao(db)