FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libgtk-3-0 \
    shared-mime-info \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Tesseract 5 (Debian trixie, the current python:3.12-slim base) ships its
# language data here; PyMuPDF's OCR needs TESSDATA_PREFIX to locate it.
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
# Resilient install: PyPI file downloads occasionally read-timeout, so use a
# generous per-request timeout and retry a few times with backoff before failing.
ENV POETRY_REQUESTS_TIMEOUT=180
RUN poetry config virtualenvs.create false \
    && { poetry install --no-interaction --no-ansi --no-root \
        || { echo "retry 1..."; sleep 10; poetry install --no-interaction --no-ansi --no-root; } \
        || { echo "retry 2..."; sleep 20; poetry install --no-interaction --no-ansi --no-root; } \
        || { echo "retry 3..."; sleep 30; poetry install --no-interaction --no-ansi --no-root; }; }

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

COPY --from=frontend-builder /app/static ./app/static/

# Drop root: run as an unprivileged user. --create-home gives WeasyPrint/fontconfig
# a writable HOME for its cache.
RUN useradd --create-home --uid 1000 appuser
USER appuser

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-${API_PORT:-8000}}"]
