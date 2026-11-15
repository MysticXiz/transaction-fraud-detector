import logging
from time import perf_counter

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.fraud_detector.api.dependencies.auth import get_current_user
from src.fraud_detector.api.dependencies.roles import require_write_access
from src.fraud_detector.api.schemas.dataset_import import (
    DatasetImportCreateSchema,
    DatasetImportJobSchema,
)
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
from src.fraud_detector.computational.ingestion.dataset_csv import (
    DatasetCsvError,
    DatasetImportCancelledError,
    DatasetTooLargeError,
)
from src.fraud_detector.config.settings import settings
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.models.dataset_import_job import (
    DatasetImportJobModel,
)
from src.fraud_detector.infrastructure.database.database import SessionLocal, get_db
from src.fraud_detector.infrastructure.repositories.dataset_repository import (
    RepositorioDataset,
)

datasets_router = APIRouter(prefix="/datasets", tags=["Datasets"])
logger = logging.getLogger(__name__)


@datasets_router.post(
    "/importacoes", response_model=DatasetImportJobSchema, status_code=201
)
def create_dataset_import(
    payload: DatasetImportCreateSchema,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    name = payload.nome.strip()
    origin = payload.origem.strip()
    if not name or not origin:
        raise HTTPException(status_code=422, detail="Nome e origem são obrigatórios")
    job = DatasetImportJobModel(
        id_usuario=current_user.id_usuario,
        nome=name,
        origem=origin,
        descricao=payload.descricao,
        nome_arquivo=payload.nome_arquivo,
        status="PENDENTE",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _import_job_response(job)


@datasets_router.get("/importacoes/{import_id}", response_model=DatasetImportJobSchema)
def get_dataset_import(
    import_id: int,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _owned_import_job(db, import_id, current_user.id_usuario)
    return _import_job_response(job)


@datasets_router.post(
    "/importacoes/{import_id}/cancelar", response_model=DatasetImportJobSchema
)
def cancel_dataset_import(
    import_id: int,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    job = _owned_import_job(db, import_id, current_user.id_usuario)
    if job.status in ("CONCLUIDO", "FALHA", "CANCELADO"):
        return _import_job_response(job)
    if job.status == "PENDENTE":
        job.status = "CANCELADO"
    else:
        job.cancelamento_solicitado = True
        job.status = "CANCELAMENTO_SOLICITADO"
    db.commit()
    db.refresh(job)
    return _import_job_response(job)


@datasets_router.post(
    "/importacoes/{import_id}/arquivo", response_model=DatasetRespostaSchema
)
def upload_dataset_import(
    import_id: int,
    arquivo: UploadFile = File(...),
    current_user: UsuarioModel = Depends(require_write_access),
    repository: RepositorioDataset = Depends(get_dataset_repository),
    db: Session = Depends(get_db),
):
    job = _owned_import_job(db, import_id, current_user.id_usuario)
    if job.status != "PENDENTE":
        raise HTTPException(status_code=409, detail="A importação não está pendente")
    if not arquivo.filename or not arquivo.filename.casefold().endswith(".csv"):
        job.status = "FALHA"
        job.mensagem_erro = "Envie um arquivo .csv"
        db.commit()
        raise HTTPException(status_code=415, detail=job.mensagem_erro)
    if arquivo.filename != job.nome_arquivo:
        job.status = "FALHA"
        job.mensagem_erro = "O arquivo recebido não corresponde à importação iniciada"
        db.commit()
        raise HTTPException(status_code=422, detail=job.mensagem_erro)

    job.status = "RECEBENDO"
    db.commit()
    should_cancel = _import_cancellation_checker(import_id)
    importer = ImportarDatasetUseCase(
        repository,
        settings.dataset_storage_path,
        max_upload_bytes=settings.max_dataset_upload_bytes,
        chunk_bytes=settings.dataset_upload_chunk_bytes,
        copy_buffer_bytes=settings.ingestion_copy_buffer_bytes,
        progress_every_rows=settings.ingestion_progress_every_rows,
    )
    try:
        dataset = importer.execute(
            stream=arquivo.file,
            filename=arquivo.filename,
            owner_id=current_user.id_usuario,
            name=job.nome,
            description=job.descricao,
            origin=job.origem,
            should_cancel=should_cancel,
            on_processing=lambda: _set_import_job_status(import_id, "PROCESSANDO"),
        )
        job = _owned_import_job(db, import_id, current_user.id_usuario)
        job.status = "CONCLUIDO"
        job.id_dataset = dataset.id_dataset
        job.mensagem_erro = None
        db.commit()
        return dataset
    except DatasetImportCancelledError as error:
        _set_import_job_status(import_id, "CANCELADO", str(error))
        raise HTTPException(
            status_code=409, detail="A importação foi cancelada"
        ) from error
    except DatasetTooLargeError as error:
        _set_import_job_status(import_id, "FALHA", str(error))
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error
    except DatasetCsvError as error:
        _set_import_job_status(import_id, "FALHA", str(error))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except FileExistsError as error:
        _set_import_job_status(import_id, "FALHA", str(error))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except IntegrityError as error:
        _set_import_job_status(
            import_id, "FALHA", "Conflito de integridade ao persistir o dataset"
        )
        constraint_name = getattr(
            getattr(error.orig, "diag", None), "constraint_name", None
        )
        if constraint_name in {
            "uk_dataset_hash",
            "dataset_hash_arquivo_key",
            "uk_dataset_usuario_hash",
        }:
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
        _set_import_job_status(import_id, "FALHA", str(error))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except Exception as error:
        _set_import_job_status(import_id, "FALHA", "Falha inesperada na importação")
        logger.exception("Falha inesperada na importação %s", import_id)
        raise HTTPException(
            status_code=500, detail="Falha inesperada na importação"
        ) from error


@datasets_router.post(
    "", response_model=DatasetRespostaSchema, status_code=status.HTTP_201_CREATED
)
def upload_dataset(
    arquivo: UploadFile = File(...),
    nome: str = Form(..., min_length=1, max_length=160),
    origem: str = Form(..., min_length=1, max_length=80),
    descricao: str | None = Form(default=None),
    current_user: UsuarioModel = Depends(require_write_access),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    if not arquivo.filename or not arquivo.filename.casefold().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Envie um arquivo .csv",
        )

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
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error
    except DatasetCsvError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except FileExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except IntegrityError as error:
        constraint_name = getattr(
            getattr(error.orig, "diag", None), "constraint_name", None
        )
        if constraint_name in {
            "uk_dataset_hash",
            "dataset_hash_arquivo_key",
            "uk_dataset_usuario_hash",
        }:
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@datasets_router.get("", response_model=list[DatasetRespostaSchema])
def list_datasets(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UsuarioModel = Depends(get_current_user),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    return GerenciarDatasetsUseCase(
        repository, settings.dataset_storage_path
    ).list_datasets(current_user.id_usuario, offset, limit)


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return DatasetDetalheSchema(
        **DatasetRespostaSchema.model_validate(dataset).model_dump(),
        amostra=[TransacaoAmostraDatasetSchema.model_validate(row) for row in sample],
    )


@datasets_router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: int,
    current_user: UsuarioModel = Depends(require_write_access),
    repository: RepositorioDataset = Depends(get_dataset_repository),
):
    try:
        GerenciarDatasetsUseCase(repository, settings.dataset_storage_path).delete(
            dataset_id, current_user.id_usuario
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset vinculado a uma execução e não pode ser excluído",
        ) from error


def _owned_import_job(db: Session, import_id: int, owner_id: int):
    job = (
        db.query(DatasetImportJobModel)
        .filter_by(id_importacao=import_id, id_usuario=owner_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada")
    return job


def _import_job_response(job: DatasetImportJobModel) -> DatasetImportJobSchema:
    return DatasetImportJobSchema(
        id_importacao=job.id_importacao,
        status=job.status,
        mensagem_erro=job.mensagem_erro,
        id_dataset=job.id_dataset,
    )


def _set_import_job_status(
    import_id: int, status_value: str, message: str | None = None
) -> None:
    with SessionLocal() as db:
        job = db.query(DatasetImportJobModel).filter_by(id_importacao=import_id).first()
        if job is None:
            logger.error("Estado da importação %s não encontrado", import_id)
            return
        if job.cancelamento_solicitado and status_value == "PROCESSANDO":
            return
        job.status = status_value
        job.mensagem_erro = message
        db.commit()


def _import_cancellation_checker(import_id: int):
    last_checked = 0.0
    cached_cancelled = False

    def should_cancel() -> bool:
        nonlocal last_checked, cached_cancelled
        now = perf_counter()
        if cached_cancelled:
            return True
        if now - last_checked < 0.5:
            return False
        last_checked = now
        with SessionLocal() as db:
            job = (
                db.query(DatasetImportJobModel)
                .filter_by(id_importacao=import_id)
                .first()
            )
            if job is None:
                logger.error("Estado da importação %s não encontrado", import_id)
                cached_cancelled = True
                return True
            cached_cancelled = job.cancelamento_solicitado or job.status in (
                "CANCELAMENTO_SOLICITADO",
                "CANCELADO",
            )
        return cached_cancelled

    return should_cancel
