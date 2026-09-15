from functools import lru_cache
from typing import List

from app.chunking.schemas import LegalDocumentChunk
from app.core.config import get_settings


class LegalChunker:
    """Segmentação de texto jurídico em blocos com sobreposição (sliding window).

    Reaproveitado de main.py sem alterações na lógica de negócio.
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.stride = chunk_size - overlap

    def chunk_text(self, texto: str) -> List[LegalDocumentChunk]:
        chunks = []
        tamanho_total = len(texto)

        for id_chunk, inicio in enumerate(range(0, tamanho_total, self.stride)):
            fim = min(inicio + self.chunk_size, tamanho_total)
            fragmento = texto[inicio:fim]

            chunk_obj = LegalDocumentChunk(
                chunk_id=id_chunk,
                texto=fragmento,
                inicio_char=inicio,
                fim_char=fim,
                tamanho=len(fragmento),
            )
            chunks.append(chunk_obj)

            if fim >= tamanho_total:
                break

        return chunks


def get_chunker(chunk_size: int | None = None, overlap: int | None = None) -> LegalChunker:
    """Fábrica do chunker. Sem argumentos, usa os defaults configurados via .env."""
    settings = get_settings()
    return LegalChunker(
        chunk_size=chunk_size or settings.chunk_size,
        overlap=overlap if overlap is not None else settings.chunk_overlap,
    )
