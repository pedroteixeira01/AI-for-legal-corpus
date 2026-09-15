from typing import List

from pydantic import BaseModel, Field

from app.chunking.schemas import LegalDocumentChunk
from app.evaluation.schemas import RougeScore


class AnonimizacaoInfo(BaseModel):
    modo: str = Field(..., description="'presidio_pt' (NER + regex) ou 'regex_only' (modo degradado)")
    ner_ativo: bool


class MetricasRouge(BaseModel):
    rouge1: RougeScore
    rouge2: RougeScore
    rougeL: RougeScore


class PipelineExecutionResult(BaseModel):
    texto_original: str
    texto_anonimizado: str
    total_chunks: int
    chunks: List[LegalDocumentChunk]
    sumario_sintetizado: str
    metricas_rouge: MetricasRouge
    anonimizacao: AnonimizacaoInfo


class ExemploResponse(BaseModel):
    texto: str
    referencia_humana: str
