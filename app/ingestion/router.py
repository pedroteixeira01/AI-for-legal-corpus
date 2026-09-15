from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.ingestion.schemas import IngestResponse
from app.ingestion.service import processar_upload

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestResponse)
async def ingerir_documento(
    file: UploadFile | None = File(default=None),
    texto: str | None = Form(default=None),
) -> IngestResponse:
    """Extrai texto de um PDF (multipart/form-data) ou aceita texto bruto diretamente
    (útil para testes sem depender de um PDF real)."""
    if file is not None:
        texto_extraido = await processar_upload(file)
        origem = "pdf"
    elif texto is not None and texto.strip():
        texto_extraido = texto
        origem = "texto_bruto"
    else:
        raise HTTPException(status_code=422, detail="Envie um arquivo PDF ('file') ou um texto bruto ('texto').")

    return IngestResponse(texto_extraido=texto_extraido, origem=origem, tamanho=len(texto_extraido))
