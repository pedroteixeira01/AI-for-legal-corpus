from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.samples import CORPUS_JURIDICO_EXEMPLO, REFERENCIA_HUMANA_GOLD
from app.ingestion.service import processar_upload
from app.pipeline.schemas import ExemploResponse, PipelineExecutionResult
from app.pipeline.service import executar_pipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/exemplo", response_model=ExemploResponse)
def obter_exemplo() -> ExemploResponse:
    """Corpus fictício e referência humana usados na demonstração da monografia —
    úteis para testar o endpoint /pipeline/process sem precisar de um PDF real."""
    return ExemploResponse(texto=CORPUS_JURIDICO_EXEMPLO, referencia_humana=REFERENCIA_HUMANA_GOLD)


@router.post("/process", response_model=PipelineExecutionResult)
async def processar_pipeline(
    referencia_humana: str = Form(..., description="Referência humana (ground truth) para o cálculo do ROUGE"),
    texto: str | None = Form(default=None, description="Texto bruto de entrada (alternativa ao upload de PDF)"),
    file: UploadFile | None = File(default=None, description="Documento PDF a ser processado"),
    chunk_size: int | None = Form(default=None, gt=0),
    overlap: int | None = Form(default=None, ge=0),
) -> PipelineExecutionResult:
    """Endpoint orquestrador: ingestão -> sanitização (LGPD) -> chunking -> síntese -> avaliação ROUGE.

    Aceita exatamente uma fonte de texto: um PDF (`file`) ou texto bruto (`texto`).
    """
    if file is not None and texto is not None:
        raise HTTPException(status_code=422, detail="Envie apenas um dos dois: 'file' (PDF) ou 'texto', não ambos.")

    if file is not None:
        texto_original = await processar_upload(file)
    elif texto is not None and texto.strip():
        texto_original = texto
    else:
        raise HTTPException(status_code=422, detail="Envie um arquivo PDF ('file') ou um texto bruto ('texto').")

    return executar_pipeline(
        texto_original=texto_original,
        referencia_humana=referencia_humana,
        chunk_size=chunk_size,
        overlap=overlap,
    )
