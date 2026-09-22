from fastapi import APIRouter, Depends, HTTPException, status
from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.dependencies.transaction import get_transaction_repository
from src.fraud_detector.api.schemas.transaction import TransacaoCriacaoSchema, TransacaoRespostaSchema, TransacaoAtualizacaoSchema
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.repositories.transaction_repository import RepositorioTransacao
from src.fraud_detector.application.use_cases.create_transaction import CriarTransacaoUseCase
from src.fraud_detector.application.use_cases.delete_transaction import ExcluirTransacaoUseCase
from src.fraud_detector.application.use_cases.get_transaction import ObterTransacaoUseCase
from src.fraud_detector.application.use_cases.update_transaction import AtualizarTransacaoUseCase

transactions_router = APIRouter(prefix="/transactions", tags=["Transactions"])

@transactions_router.post("", response_model=TransacaoRespostaSchema, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction_data: TransacaoCriacaoSchema, _: UsuarioModel = Depends(get_current_user), repository: RepositorioTransacao = Depends(get_transaction_repository)):
    return CriarTransacaoUseCase(repository).execute(transaction_data)

@transactions_router.get("", response_model=list[TransacaoRespostaSchema])
def get_transactions(_: UsuarioModel = Depends(get_current_user), repository: RepositorioTransacao = Depends(get_transaction_repository)):
    return ObterTransacaoUseCase(repository).get_all()

@transactions_router.get("/{id_transacao}", response_model=TransacaoRespostaSchema)
def get_transaction(id_transacao: int, _: UsuarioModel = Depends(get_current_user), repository: RepositorioTransacao = Depends(get_transaction_repository)):
    transaction = ObterTransacaoUseCase(repository).get_by_id(id_transacao)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")
    return transaction

@transactions_router.patch("/{id_transacao}", response_model=TransacaoRespostaSchema)
def update_transaction(id_transacao: int, transaction_data: TransacaoAtualizacaoSchema, _: UsuarioModel = Depends(get_current_user), repository: RepositorioTransacao = Depends(get_transaction_repository)):
    try:
        return AtualizarTransacaoUseCase(repository).execute(id_transacao, transaction_data)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND if str(error) == "Transação não encontrada" else status.HTTP_400_BAD_REQUEST, detail=str(error))

@transactions_router.delete("/{id_transacao}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(id_transacao: int, _: UsuarioModel = Depends(get_current_user), repository: RepositorioTransacao = Depends(get_transaction_repository)):
    try:
        ExcluirTransacaoUseCase(repository).execute(id_transacao)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")