from pathlib import Path
from typing import Annotated

from pydantic import (
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# O diretório-base permite carregar o .env do projeto independentemente do diretório do processo.
BASE_DIR = Path(__file__).resolve().parents[4]
MIB = 1024 * 1024
MAX_UPLOAD_LIMIT_MIB = 10 * 1024


class Settings(BaseSettings):
    """Configurações de infraestrutura carregadas de variáveis de ambiente."""

    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    database_url: str | None = None
    database_host: str | None = None
    postgres_user: str = "fraud"
    postgres_password: str | None = None
    postgres_db: str = "fraud_detection"
    postgres_port: int = 5432
    auth_cookie_secure: bool = False
    bootstrap_admin_email: EmailStr | None = None
    bootstrap_admin_password: (
        Annotated[str, StringConstraints(min_length=12, max_length=128)] | None
    ) = None
    dataset_storage_path: Path = BASE_DIR / "storage" / "datasets"
    max_dataset_upload_bytes: int = Field(
        default=200 * MIB, ge=MIB, le=MAX_UPLOAD_LIMIT_MIB * MIB
    )
    dataset_upload_chunk_bytes: int = 1024 * 1024
    ingestion_copy_buffer_bytes: int = 1024 * 1024
    ingestion_progress_every_rows: int = 50_000
    cors_origins: list[str] = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        hide_input_in_errors=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def configure_database(self) -> "Settings":
        if self.database_url is None:
            if not self.database_host or not self.postgres_password:
                raise ValueError(
                    "Configure DATABASE_URL ou DATABASE_HOST e POSTGRES_PASSWORD"
                )
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.database_host,
                port=self.postgres_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)
        return self


# Uma única instância evita que cada módulo leia e interprete o ambiente novamente.
settings = Settings()
