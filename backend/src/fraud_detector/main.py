from fastapi import FastAPI

from src.fraud_detector.infrastructure import models
from src.fraud_detector.api.routes.auth import auth_router
from src.fraud_detector.api.routes.transactions import transactions_router

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

routes = [auth_router, transactions_router]

for route in routes:
    app.include_router(route)
