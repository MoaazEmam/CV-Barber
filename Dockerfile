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
    wget \
    ca-certificates \
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
    fonts-texgyre \
    fonts-liberation \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Tesseract 5 (Debian trixie, the current python:3.12-slim base) ships its
# language data here; PyMuPDF's OCR needs TESSDATA_PREFIX to locate it.
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Tectonic — installed as a static (musl) binary straight from the GitHub
# release, NOT via apt, so we avoid pulling in the full TexLive dependency tree.
# Tectonic fetches and caches LaTeX packages on first use; we prime that cache at
# build time (below) so the first user's compile isn't slow.
ARG TECTONIC_VERSION=0.15.0
RUN wget -q "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic@${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" -O /tmp/tectonic.tar.gz \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && rm /tmp/tectonic.tar.gz \
    && chmod +x /usr/local/bin/tectonic \
    && tectonic --version

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

# Warm the Tectonic package cache into this layer, as appuser so it lands in the
# same HOME cache the runtime uses. The first real CV compile is then fast.
RUN tectonic --chatter minimal --outdir /tmp app/pipeline/pdf/warmup.tex && rm -f /tmp/warmup.*

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-${API_PORT:-8000}}"]
