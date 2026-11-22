from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine, false, select
from src.fraud_detector.config.settings import settings

# O engine e a fábrica de sessões são compartilhados pela aplicação inteira.
assert settings.database_url is not None
engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)

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


def check_schema() -> None:
    """Verifica se as tabelas e colunas mapeadas estão acessíveis."""
    from src.fraud_detector.infrastructure import models  # noqa: F401

    # Valida os nomes em uma única consulta, sem ler registros nem exigir um stamp.
    probe = select(
        *(
            select(table).where(false()).exists()
            for table in Base.metadata.tables.values()
        )
    )
    with engine.connect() as connection:
        connection.execute(probe)
