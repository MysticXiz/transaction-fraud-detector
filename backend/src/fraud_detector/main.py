import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.fraud_detector.infrastructure import models  # noqa: F401
from src.fraud_detector.config.settings import settings
from src.fraud_detector.infrastructure.database.database import (
    SessionLocal,
    test_connection,
)
from src.fraud_detector.infrastructure.seed_admin import seed_bootstrap_admin
from src.fraud_detector.api.routes.auth import auth_router
from src.fraud_detector.api.routes.datasets import datasets_router
from src.fraud_detector.api.routes.analyses import analyses_router, models_router
from src.fraud_detector.api.routes.benchmarks import benchmarks_router
from src.fraud_detector.api.routes.transactions import transactions_router

logging.getLogger("fraud_detector").setLevel(logging.INFO)
if not logging.getLogger("fraud_detector").handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    logging.getLogger("fraud_detector").addHandler(_handler)
    logging.getLogger("fraud_detector").propagate = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_bootstrap_admin(db)
        yield
    finally:
        db.close()


# A aplicação concentra apenas a composição da API; regras de negócio ficam nas camadas abaixo.
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}


@app.get("/health")
def health_check():
    test_connection()
    return {"status": "ok"}


# Manter os routers em uma lista deixa explícito quais módulos estão publicados no bootstrap.
routes = [
    auth_router,
    transactions_router,
    datasets_router,
    analyses_router,
    benchmarks_router,
    models_router,
]

for route in routes:
    app.include_router(route)
