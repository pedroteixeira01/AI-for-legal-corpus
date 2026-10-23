from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.summarization.service import SummarizerError


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version)

    app.include_router(api_v1_router, prefix="/v1")

    @app.exception_handler(SummarizerError)
    def summarizer_error_handler(request: Request, exc: SummarizerError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    return app
