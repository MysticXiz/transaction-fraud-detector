import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.fraud_detector.infrastructure import models
from src.fraud_detector.api.routes.auth import auth_router
from src.fraud_detector.api.routes.datasets import datasets_router
from src.fraud_detector.api.routes.transactions import transactions_router

logging.getLogger("fraud_detector").setLevel(logging.INFO)
if not logging.getLogger("fraud_detector").handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logging.getLogger("fraud_detector").addHandler(_handler)
    logging.getLogger("fraud_detector").propagate = True

# A aplicação concentra apenas a composição da API; regras de negócio ficam nas camadas abaixo.
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

# Manter os routers em uma lista deixa explícito quais módulos estão publicados no bootstrap.
routes = [auth_router, transactions_router, datasets_router]

for route in routes: app.include_router(route)