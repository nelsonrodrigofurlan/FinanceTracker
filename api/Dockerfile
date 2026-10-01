# FinanceTracker API + Pipeline Job (mesma imagem, entrypoints diferentes)
#   Serviço:  CMD padrão (uvicorn)
#   Job:      gcloud run jobs ... --command=python --args=-m,ft.pipeline

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependências primeiro (cache de camada), versões travadas pelo uv.lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runner
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH" PORT=8080
RUN groupadd --system --gid 1001 app && useradd --system --uid 1001 --gid app --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn ft.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-server-header"]
