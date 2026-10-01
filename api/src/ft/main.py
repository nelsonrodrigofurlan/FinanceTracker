import logging

from fastapi import FastAPI

from ft import __version__
from ft.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="FinanceTracker API",
        version=__version__,
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
    )

    @app.get("/health", tags=["infra"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    return app


app = create_app()
