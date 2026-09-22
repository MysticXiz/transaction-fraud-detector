from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine, text
from src.fraud_detector.config.settings import settings


engine = create_engine(
    settings.database_url,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

def test_connection():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))