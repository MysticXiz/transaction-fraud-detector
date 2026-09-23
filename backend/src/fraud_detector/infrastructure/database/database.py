from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine, text
from src.fraud_detector.config.settings import settings

# O engine e a fábrica de sessões são compartilhados pela aplicação inteira.
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
    """Fornece uma sessão por requisição e garante seu fechamento ao final."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

def test_connection():
    """Executa uma consulta mínima para verificar a conectividade com o banco."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))