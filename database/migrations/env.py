from alembic import context


def run_migrations_offline() -> None:
    context.configure(dialect_name="postgresql", literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from src.fraud_detector.infrastructure import models  # noqa: F401
    from src.fraud_detector.infrastructure.database.database import Base, engine

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
