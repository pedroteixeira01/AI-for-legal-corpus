from fastapi import APIRouter

from app.summarization.schemas import SummarizeRequest, SummarizeResponse
from app.summarization.service import get_summarizer

router = APIRouter(prefix="/summarize", tags=["summarization"])


@router.post("", response_model=SummarizeResponse)
def sumarizar_chunks(payload: SummarizeRequest) -> SummarizeResponse:
    """Sintetiza uma lista de chunks (implementação mock — ver BaseSummarizer)."""
    summarizer = get_summarizer()
    sumario = summarizer.sintetizar_chunks(payload.chunks)
    return SummarizeResponse(sumario_sintetizado=sumario, modelo=summarizer.model_name)
