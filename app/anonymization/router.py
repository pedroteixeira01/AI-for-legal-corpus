from fastapi import APIRouter

from app.anonymization.schemas import AnonymizeRequest, AnonymizeResponse
from app.anonymization.service import get_anonymizer

router = APIRouter(prefix="/anonymize", tags=["anonymization"])


@router.post("", response_model=AnonymizeResponse)
def anonimizar_texto(payload: AnonymizeRequest) -> AnonymizeResponse:
    """Anonimiza um texto (Presidio em português + regex complementar de CPF)."""
    anonymizer = get_anonymizer()
    entidades = anonymizer.analisar(payload.texto)
    texto_anonimizado = anonymizer.sanitizar(payload.texto)
    return AnonymizeResponse(
        texto_anonimizado=texto_anonimizado,
        modo=anonymizer.modo,
        ner_ativo=anonymizer.ner_ativo,
        entidades_detectadas=entidades,
    )
