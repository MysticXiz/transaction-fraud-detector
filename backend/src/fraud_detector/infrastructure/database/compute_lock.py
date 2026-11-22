from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text

from src.fraud_detector.infrastructure.database.database import engine

# Identifica o recurso de execução de análises e calibração OpenCL neste banco.
_LOCK_KEY = 6_274_119_803


@contextmanager
def try_compute_lock() -> Iterator[bool]:
    if engine.dialect.name != "postgresql":
        yield True
        return

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        params = {"key": _LOCK_KEY}
        acquired = bool(
            connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), params)
        )
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), params)
                except Exception:
                    connection.invalidate()
                    raise
