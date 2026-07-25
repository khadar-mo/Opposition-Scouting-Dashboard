# Single production image: FastAPI serves both the API and the built frontend.
# The pipeline/ml packages run locally (they need the raw data + a GPU-free
# PyTorch install that has no place in the serving image).

FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM python:3.12-slim AS api
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Workspace manifests first so dependency layers cache well.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY pipeline/pyproject.toml pipeline/pyproject.toml
COPY ml/pyproject.toml ml/pyproject.toml
RUN uv sync --frozen --package scout-backend --no-dev --no-install-workspace

COPY backend/src backend/src
RUN uv sync --frozen --package scout-backend --no-dev

COPY --from=frontend /web/dist /app/static
ENV STATIC_DIR=/app/static
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
