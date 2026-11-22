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
from src.fraud_detector.infrastructure.upload_settings import get_upload_limit
from src.fraud_detector.infrastructure.models.user import UsuarioModel
from src.fraud_detector.infrastructure.models.dataset_import_job import (
    DatasetImportJobModel,
)
from src.fraud_detector.infrastructure.database.database import SessionLocal, get_db
from src.fraud_detector.infrastructure.repositories.dataset_import_repository import (
    RepositorioImportacaoDataset,
    try_import_upload,
)
from src.fraud_detector.infrastructure.repositories.dataset_repository import (
    RepositorioDataset,
)

datasets_router = APIRouter(prefix="/datasets", tags=["Datasets"])
logger = logging.getLogger(__name__)


@datasets_router.get("/limite-upload", dependencies=[Depends(require_write_access)])
def upload_limit() -> dict[str, int]:
    return {"limite_bytes": get_upload_limit()}


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
    jobs = RepositorioImportacaoDataset(db, import_id, current_user.id_usuario)
    job = _require_import_job(jobs.get_with_recovery())
    response = _import_job_response(job)
    db.commit()
    return response


@datasets_router.post(
    "/importacoes/{import_id}/cancelar", response_model=DatasetImportJobSchema
)
def cancel_dataset_import(
    import_id: int,
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    jobs = RepositorioImportacaoDataset(db, import_id, current_user.id_usuario)
    job = _require_import_job(jobs.get(lock=True))
    jobs.cancel(job)
    response = _import_job_response(job)
    db.commit()
    return response


@datasets_router.post(
    "/importacoes/{import_id}/arquivo", response_model=DatasetRespostaSchema
)
def upload_dataset_import(
    import_id: int,
    arquivo: UploadFile = File(...),
    current_user: UsuarioModel = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    owner_id = current_user.id_usuario
    _require_import_job(RepositorioImportacaoDataset(db, import_id, owner_id).get())
    # Release the auth/read transaction before checking out the upload connection.
    db.rollback()
    with try_import_upload(import_id) as upload_db:
        if upload_db is None:
            raise HTTPException(
                status_code=409, detail="A importação não está pendente"
            )
        return _run_dataset_import(upload_db, import_id, owner_id, arquivo)


def _run_dataset_import(
    db: Session, import_id: int, owner_id: int, arquivo: UploadFile
) -> DatasetRespostaSchema:
    jobs = RepositorioImportacaoDataset(db, import_id, owner_id)
    job = _require_import_job(jobs.get(lock=True))
    if job.status != "PENDENTE":
        raise HTTPException(status_code=409, detail="A importação não está pendente")

    filename = arquivo.filename
    if not filename or not filename.casefold().endswith(".csv"):
        validation_error = HTTPException(
            status_code=415, detail="Envie um arquivo .csv"
        )
    elif filename != job.nome_arquivo:
        validation_error = HTTPException(
            status_code=422,
            detail="O arquivo recebido não corresponde à importação iniciada",
        )
    else:
        validation_error = None
    if validation_error is not None:
        job.status = "FALHA"
        job.mensagem_erro = validation_error.detail
        db.commit()
        raise validation_error

    name, description, origin = job.nome, job.descricao, job.origem
    job.status = "RECEBENDO"
    try:
        db.commit()
        dataset = ImportarDatasetUseCase(
            RepositorioDataset(db, stage_import_completion=jobs.stage_completion),
            settings.dataset_storage_path,
            max_upload_bytes=get_upload_limit(),
            chunk_bytes=settings.dataset_upload_chunk_bytes,
            copy_buffer_bytes=settings.ingestion_copy_buffer_bytes,
            progress_every_rows=settings.ingestion_progress_every_rows,
        ).execute(
            stream=arquivo.file,
            filename=filename,
            owner_id=owner_id,
            name=name,
            description=description,
            origin=origin,
            should_cancel=_import_cancellation_checker(import_id, owner_id),
            on_processing=jobs.begin_processing,
        )
        response = DatasetRespostaSchema.model_validate(dataset)
        db.commit()
        return response
    except Exception as error:
        http_error, message = _import_upload_error(error)
        try:
            db.rollback()
            cancelled = jobs.finish_error(message)
            db.commit()
        except Exception:
            logger.exception(
                "Falha ao registrar o resultado da importação %s", import_id
            )
        else:
            if cancelled:
                http_error = HTTPException(
                    status_code=409, detail="A importação foi cancelada"
                )
        raise http_error from error


def _import_upload_error(error: Exception) -> tuple[HTTPException, str]:
    if isinstance(error, (DatasetImportCancelledError, FileExistsError)):
        return HTTPException(status_code=409, detail=str(error)), str(error)
    if isinstance(error, DatasetTooLargeError):
        return HTTPException(status_code=413, detail=str(error)), str(error)
    if isinstance(error, ValueError):
        return HTTPException(status_code=422, detail=str(error)), str(error)
    if isinstance(error, IntegrityError):
        message = "Conflito de integridade ao persistir o dataset"
        constraint_name = getattr(
            getattr(error.orig, "diag", None), "constraint_name", None
        )
        if constraint_name in {
            "uk_dataset_hash",
            "dataset_hash_arquivo_key",
            "uk_dataset_usuario_hash",
        }:
            return (
                HTTPException(status_code=409, detail="Este arquivo já foi importado"),
                message,
            )
        logger.exception("Conflito de integridade ao importar dataset")
        return (
            HTTPException(
                status_code=409, detail=f"{message}. Consulte o log do backend."
            ),
            message,
        )
    message = "Falha inesperada na importação"
    logger.exception(message)
    return HTTPException(status_code=500, detail=message), message


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
            max_upload_bytes=get_upload_limit(),
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


def _require_import_job(job: DatasetImportJobModel | None) -> DatasetImportJobModel:
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


def _import_cancellation_checker(import_id: int, owner_id: int):
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
            job = RepositorioImportacaoDataset(db, import_id, owner_id).get()
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
