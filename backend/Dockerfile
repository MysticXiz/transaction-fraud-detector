FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libopencl1 ocl-icd-libopencl1 ocl-icd-opencl-dev pocl-opencl-icd clinfo curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r backend/requirements.txt

COPY backend ./backend
COPY pyproject.toml ./pyproject.toml

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage/datasets \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.fraud_detector.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]
