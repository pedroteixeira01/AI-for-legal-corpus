from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    sumario_gerado: str = Field(..., description="Síntese produzida pelo modelo")
    referencia_humana: str = Field(..., description="Referência humana (ground truth) para comparação")


class RougeScore(BaseModel):
    precision: float
    recall: float
    fmeasure: float


class EvaluateResponse(BaseModel):
    rouge1: RougeScore
    rouge2: RougeScore
    rougeL: RougeScore
