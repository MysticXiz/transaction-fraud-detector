import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.dependencies.dataset import get_dataset_repository
from src.fraud_detector.api.schemas.dataset import (
    DatasetDetalheSchema,
    DatasetRespostaSchema,
    TransacaoAmostraDatasetSchema,
)
from src.fraud_detector.application.use_cases.manage_datasets import (
    GerenciarDatasetsUseCase,
    ImportarDatasetUseCase,
)
from src.fraud_detector.computational.ingestion.dataset_csv import DatasetCsvError, DatasetTooLargeError
from src.fraud_detector.config.settings import settings
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.repositories.dataset_repository import RepositorioDataset


datasets_router = APIRouter(prefix="/datasets", tags=["Datasets"])
logger = logging.getLogger(__name__)


@datasets_router.post("", response_model=DatasetRespostaSchema, status_code=status.HTTP_201_CREATED)
def upload_dataset(
    arquivo: UploadFile = File(...),
    nome: str = Form(..., min_length=1, max_length=160),
    origem: str = Form(..., min_length=1, max_length=80),
    descricao: str | None = Form(default=None),
    current_user: UsuarioModel = Depends(get_current_user),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    if not arquivo.filename or not arquivo.filename.casefold().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Envie um arquivo .csv")

    try:
        return ImportarDatasetUseCase(
            repository,
            settings.dataset_storage_path,
            max_upload_bytes=settings.max_dataset_upload_bytes,
            chunk_bytes=settings.dataset_upload_chunk_bytes,
            copy_buffer_bytes=settings.ingestion_copy_buffer_bytes,
            progress_every_rows=settings.ingestion_progress_every_rows,
        ).execute(
            stream=arquivo.file,
            filename=arquivo.filename,
            owner_id=current_user.id_usuario,
            name=nome,
            description=descricao,
            origin=origem,
        )
    except DatasetTooLargeError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from error
    except DatasetCsvError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except FileExistsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except IntegrityError as error:
        constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint_name == "uk_dataset_hash":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este arquivo já foi importado",
            ) from error
        logger.exception("Conflito de integridade ao importar dataset")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflito de integridade ao persistir o dataset. Consulte o log do backend.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@datasets_router.get("", response_model=list[DatasetRespostaSchema])
def list_datasets(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UsuarioModel = Depends(get_current_user),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    return GerenciarDatasetsUseCase(repository, settings.dataset_storage_path).list_datasets(
        current_user.id_usuario, offset, limit
    )


@datasets_router.get("/{dataset_id}", response_model=DatasetDetalheSchema)
def get_dataset(
    dataset_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    try:
        dataset, sample = GerenciarDatasetsUseCase(
            repository, settings.dataset_storage_path
        ).get(dataset_id, current_user.id_usuario)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return DatasetDetalheSchema(
        **DatasetRespostaSchema.model_validate(dataset).model_dump(),
        amostra=[TransacaoAmostraDatasetSchema.model_validate(row) for row in sample],
    )


@datasets_router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    try:
        GerenciarDatasetsUseCase(repository, settings.dataset_storage_path).delete(
            dataset_id, current_user.id_usuario
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset vinculado a uma execução e não pode ser excluído",
        ) from error
