from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version)

    app.include_router(api_v1_router, prefix="/v1")

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    return app
