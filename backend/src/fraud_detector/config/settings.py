from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# O diretório-base permite carregar o .env do projeto independentemente do diretório do processo.
BASE_DIR = Path(__file__).resolve().parents[4]

class Settings(BaseSettings):
    """Configurações de infraestrutura carregadas de variáveis de ambiente."""
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    database_url: str
    dataset_storage_path: Path = BASE_DIR / "storage" / "datasets"
    max_dataset_upload_bytes: int = 200 * 1024 * 1024
    dataset_upload_chunk_bytes: int = 1024 * 1024
    ingestion_copy_buffer_bytes: int = 1024 * 1024
    ingestion_progress_every_rows: int = 50_000

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

# Uma única instância evita que cada módulo leia e interprete o ambiente novamente.
settings = Settings()