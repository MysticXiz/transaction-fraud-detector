import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.fraud_detector.config.settings import MIB, MAX_UPLOAD_LIMIT_MIB, settings


def _settings_path() -> Path:
    return settings.dataset_storage_path / ".upload-limit"


def get_upload_limit() -> int:
    try:
        value = int(_settings_path().read_text(encoding="ascii"))
    except FileNotFoundError:
        return settings.max_dataset_upload_bytes
    if not MIB <= value <= MAX_UPLOAD_LIMIT_MIB * MIB:
        raise ValueError("Limite de upload persistido fora da faixa permitida")
    return value


def save_upload_limit(limit_bytes: int) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = NamedTemporaryFile(dir=path.parent, delete=False)
    temp_path = Path(temporary.name)
    try:
        with temporary:
            temporary.write(f"{limit_bytes}\n".encode("ascii"))
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
