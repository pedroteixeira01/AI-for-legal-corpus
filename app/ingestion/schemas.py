from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    texto_extraido: str = Field(..., description="Texto (Markdown) extraído do documento")
    origem: str = Field(..., description="'pdf' ou 'texto_bruto'")
    tamanho: int
