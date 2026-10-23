import re

import pymupdf
import pymupdf4llm
from fastapi import HTTPException, UploadFile

# Ligaduras tipográficas que alguns PDFs codificam como caracteres de uso privado (ou
# como os glifos de apresentação U+FB01/U+FB02) e que a extração entrega como lixo,
# geralmente seguidos de um espaço espúrio: "instituições \ue00b nanceiras".
LIGADURAS = {
    "\ue000": "fi", "\ue00b": "fi", "\ufb01": "fi",
    "\ue001": "fl", "\ue00c": "fl", "\ufb02": "fl",
    "\ue00d": "Th",
    "\ue002": "ff", "\ue00e": "ff",
}  # fmt: skip
_RE_LIGADURA = re.compile("([" + "".join(LIGADURAS) + "]) ?")


def normalizar_ligaduras(texto: str) -> str:
    """Converte os caracteres de ligadura em letras, consumindo o espaço espúrio logo após eles."""
    return _RE_LIGADURA.sub(lambda m: LIGADURAS[m.group(1)], texto)


def extrair_texto_pdf(conteudo: bytes) -> str:
    """Extrai o texto de um PDF em Markdown limpo via PyMuPDF4LLM.

    Levanta HTTPException(422) se o conteúdo não puder ser interpretado
    como um PDF válido.
    """
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo PDF vazio.")

    try:
        documento = pymupdf.open(stream=conteudo, filetype="pdf")
    except Exception as exc:  # arquivo corrompido ou não é um PDF
        raise HTTPException(status_code=422, detail=f"Não foi possível ler o PDF: {exc}") from exc

    try:
        texto = pymupdf4llm.to_markdown(documento)
    finally:
        documento.close()

    if not texto.strip():
        raise HTTPException(status_code=422, detail="Nenhum texto pôde ser extraído do PDF.")

    return normalizar_ligaduras(texto)


async def processar_upload(file: UploadFile) -> str:
    """Valida o content-type do upload e delega a extração para PyMuPDF4LLM."""
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de arquivo não suportado: {file.content_type}. Envie um PDF.",
        )
    conteudo = await file.read()
    return extrair_texto_pdf(conteudo)
