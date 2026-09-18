from fastapi import Depends
from sqlalchemy.orm import Session
from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.repositories.transaction_repository import TransactionRepository

def get_transaction_repository(db: Session = Depends(get_db)) -> TransactionRepository:
    return TransactionRepository(db)