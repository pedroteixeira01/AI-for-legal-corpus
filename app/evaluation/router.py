from fastapi import APIRouter

from app.evaluation.schemas import EvaluateRequest, EvaluateResponse
from app.evaluation.service import get_evaluator

router = APIRouter(prefix="/evaluate", tags=["evaluation"])


@router.post("", response_model=EvaluateResponse)
def avaliar_sumario(payload: EvaluateRequest) -> EvaluateResponse:
    """Calcula as métricas ROUGE-1, ROUGE-2 e ROUGE-L entre a síntese gerada e a referência humana."""
    evaluator = get_evaluator()
    metricas = evaluator.calcular_metricas(payload.sumario_gerado, payload.referencia_humana)
    return EvaluateResponse(**metricas)
