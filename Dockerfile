FROM python:3.12-slim

# weasyprint needs these system dependencies
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# install poetry
RUN pip install poetry --no-cache-dir

# copy dependency files first (better layer caching)
COPY pyproject.toml poetry.lock ./

# install dependencies only (no dev deps, no virtualenv inside container)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# copy application code
COPY app/ ./app/

# expose port
EXPOSE 8000

# run with single worker (scale via multiple containers, not workers)
CMD uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}