FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS deps
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir "poetry==2.4.1"

COPY pyproject.toml poetry.lock ./

ENV POETRY_REQUESTS_TIMEOUT=180
RUN poetry config virtualenvs.in-project true \
    && { poetry install --only main --no-interaction --no-ansi --no-root \
        || { echo "retry 1..."; sleep 10; poetry install --only main --no-interaction --no-ansi --no-root; } \
        || { echo "retry 2..."; sleep 20; poetry install --only main --no-interaction --no-ansi --no-root; } \
        || { echo "retry 3..."; sleep 30; poetry install --only main --no-interaction --no-ansi --no-root; }; }

# Tectonic — static (musl) binary straight from the GitHub release (NOT apt, which
# would pull the full TexLive tree). Tectonic fetches/caches LaTeX packages on
# first use; the runtime stage primes that cache so the first compile is fast.
ARG TECTONIC_VERSION=0.15.0
RUN wget -q "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic@${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" -O /tmp/tectonic.tar.gz \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && rm /tmp/tectonic.tar.gz \
    && chmod +x /usr/local/bin/tectonic

FROM python:3.12-slim AS runtime
WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    shared-mime-info \
    tesseract-ocr \
    tesseract-ocr-eng \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Tesseract 5 (Debian trixie) ships its language data here; PyMuPDF's OCR needs
# TESSDATA_PREFIX to locate it.
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
# Run the app out of the copied virtualenv.
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=deps /app/.venv /app/.venv
COPY --from=deps /usr/local/bin/tectonic /usr/local/bin/tectonic

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY --from=frontend-builder /app/static ./app/static/

# Drop root: run as an unprivileged user. --create-home gives WeasyPrint/fontconfig
# (and Tectonic's cache) a writable HOME.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# Warm the Tectonic package cache into this layer, as appuser so it lands in the
# same HOME cache the runtime uses. The first real CV compile is then fast.
RUN tectonic --chatter minimal --outdir /tmp app/pipeline/pdf/warmup.tex && rm -f /tmp/warmup.*

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-${API_PORT:-8000}}"]
