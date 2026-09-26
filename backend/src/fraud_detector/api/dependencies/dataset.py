from fastapi import Depends
from sqlalchemy.orm import Session

from src.fraud_detector.infrastructure.database.database import get_db
from src.fraud_detector.infrastructure.repositories.dataset_repository import RepositorioDataset


def get_dataset_repository(db: Session = Depends(get_db)) -> RepositorioDataset:
    return RepositorioDataset(db)