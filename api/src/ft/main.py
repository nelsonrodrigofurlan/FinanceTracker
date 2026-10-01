import logging
from typing import Annotated

from fastapi import Depends, FastAPI

from ft import __version__
from ft.auth import CurrentUser, require_user
from ft.config import get_settings
from ft.market_api import router as market_router


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

    @app.get("/me", tags=["auth"])
    def me(user: Annotated[CurrentUser, Depends(require_user)]) -> dict[str, str]:
        return {"user_id": user.user_id, "aal": user.aal}

    app.include_router(market_router)

    return app


app = create_app()
