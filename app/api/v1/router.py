from fastapi import APIRouter

from app.anonymization.router import router as anonymization_router
from app.chunking.router import router as chunking_router
from app.evaluation.router import router as evaluation_router
from app.ingestion.router import router as ingestion_router
from app.pipeline.router import router as pipeline_router
from app.summarization.router import router as summarization_router

api_v1_router = APIRouter()

# Endpoint orquestrador (essencial)
api_v1_router.include_router(pipeline_router)

# Endpoints por etapa (bônus didático)
api_v1_router.include_router(ingestion_router)
api_v1_router.include_router(anonymization_router)
api_v1_router.include_router(chunking_router)
api_v1_router.include_router(summarization_router)
api_v1_router.include_router(evaluation_router)
