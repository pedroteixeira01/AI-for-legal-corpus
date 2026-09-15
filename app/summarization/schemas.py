from typing import List

from pydantic import BaseModel, Field

from app.chunking.schemas import LegalDocumentChunk


class SummarizeRequest(BaseModel):
    chunks: List[LegalDocumentChunk] = Field(..., description="Chunks previamente gerados pela etapa de chunking")


class SummarizeResponse(BaseModel):
    sumario_sintetizado: str
    modelo: str
