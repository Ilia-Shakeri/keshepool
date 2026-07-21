# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev libmagic1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install -r requirements.txt

RUN adduser --disabled-password --gecos "" appuser

COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini
COPY ./scripts ./scripts
COPY ./entrypoint.sh ./entrypoint.sh

RUN mkdir -p /app/static \
    && chown -R appuser:appuser /app \
    && chmod +x /app/entrypoint.sh

USER appuser

CMD ["/app/entrypoint.sh"]
