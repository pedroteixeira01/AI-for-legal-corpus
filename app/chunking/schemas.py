from typing import List

from pydantic import BaseModel, Field


class LegalDocumentChunk(BaseModel):
    chunk_id: int
    texto: str = Field(..., description="Fragmento isolado e sanitizado do texto jurídico")
    inicio_char: int
    fim_char: int
    tamanho: int


class ChunkRequest(BaseModel):
    texto: str = Field(..., description="Texto já sanitizado a ser segmentado")
    chunk_size: int | None = Field(
        default=None, gt=0, description="Tamanho da janela em caracteres (padrão: CHUNK_SIZE)"
    )
    overlap: int | None = Field(
        default=None, ge=0, description="Sobreposição entre janelas consecutivas (padrão: CHUNK_OVERLAP)"
    )


class ChunkResponse(BaseModel):
    total_chunks: int
    chunk_size: int
    overlap: int
    chunks: List[LegalDocumentChunk]
