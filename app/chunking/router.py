from fastapi import APIRouter, HTTPException

from app.chunking.schemas import ChunkRequest, ChunkResponse
from app.chunking.service import get_chunker

router = APIRouter(prefix="/chunk", tags=["chunking"])


@router.post("", response_model=ChunkResponse)
def chunk_texto(payload: ChunkRequest) -> ChunkResponse:
    """Segmenta um texto (já sanitizado) em blocos com sobreposição configurável, cortando em fim de frase."""
    try:
        chunker = get_chunker(chunk_size=payload.chunk_size, overlap=payload.overlap)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    chunks = chunker.chunk_text(payload.texto)
    return ChunkResponse(
        total_chunks=len(chunks),
        chunk_size=chunker.chunk_size,
        overlap=chunker.overlap,
        chunks=chunks,
    )
