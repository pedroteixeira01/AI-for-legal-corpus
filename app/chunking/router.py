from fastapi import APIRouter

from app.chunking.schemas import ChunkRequest, ChunkResponse
from app.chunking.service import get_chunker

router = APIRouter(prefix="/chunk", tags=["chunking"])


@router.post("", response_model=ChunkResponse)
def chunk_texto(payload: ChunkRequest) -> ChunkResponse:
    """Segmenta um texto (já sanitizado) em blocos com sobreposição configurável."""
    chunker = get_chunker(chunk_size=payload.chunk_size, overlap=payload.overlap)
    chunks = chunker.chunk_text(payload.texto)
    return ChunkResponse(
        total_chunks=len(chunks),
        chunk_size=chunker.chunk_size,
        overlap=chunker.overlap,
        chunks=chunks,
    )
