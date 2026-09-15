from typing import List

from pydantic import BaseModel, Field


class EntidadeDetectada(BaseModel):
    tipo: str = Field(..., description="Tipo de entidade sensível (ex.: PERSON, BR_CPF)")
    inicio: int
    fim: int
    score: float


class AnonymizeRequest(BaseModel):
    texto: str = Field(..., description="Texto bruto a ser anonimizado")


class AnonymizeResponse(BaseModel):
    texto_anonimizado: str
    modo: str = Field(..., description="'presidio_pt' (NER + regex) ou 'regex_only' (modo degradado)")
    ner_ativo: bool
    entidades_detectadas: List[EntidadeDetectada] = Field(default_factory=list)
