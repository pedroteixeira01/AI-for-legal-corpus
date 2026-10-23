import re
from bisect import bisect_left, bisect_right
from typing import List

from app.chunking.schemas import LegalDocumentChunk
from app.core.config import get_settings

# Abreviações jurídicas comuns cujo ponto final não encerra uma frase
# (comparação sem diferenciar maiúsculas, contra o token inteiro que precede o ponto).
ABREVIACOES = frozenset(
    {
        "art.", "arts.", "fl.", "fls.", "n.", "nº.", "des.", "min.", "rel.", "dr.", "dra.",
        "sr.", "sra.", "s.a.", "ltda.", "inc.", "p.", "cf.", "v.g.", "e.g.",
    }
)  # fmt: skip

_TERMINADORES = re.compile(r"[.;!?\n]")
_INICIO_DE_PALAVRA = re.compile(r"(?<=\s)\S")
_ESPACOS = re.compile(r"\s*")
_ABRE_TOKEN = "([{\"'“‘«"


def _e_abreviacao(texto: str, pos_ponto: int) -> bool:
    """True se o ponto em `pos_ponto` fecha uma abreviação da lista ABREVIACOES."""
    ini = pos_ponto
    while ini > 0 and not texto[ini - 1].isspace():
        ini -= 1
    token = texto[ini : pos_ponto + 1].lstrip(_ABRE_TOKEN).lower()
    return token in ABREVIACOES


def _inicios_de_frase(texto: str) -> List[int]:
    """Posições onde uma nova frase começa.

    Um limite é um de `. ; ! ?` ou quebra de linha, seguido de espaço e letra
    maiúscula, ou de nova linha — exceto quando o ponto fecha uma abreviação.
    A posição devolvida é a da primeira letra da frase seguinte.
    """
    n = len(texto)
    inicios = set()
    for m in _TERMINADORES.finditer(texto):
        i = m.start()
        espacos = _ESPACOS.match(texto, i + 1)
        fim_espacos = espacos.end()
        if fim_espacos >= n:
            continue
        ws = espacos.group()
        if "\n" not in ws and not (ws and texto[fim_espacos].isupper()):
            continue
        if texto[i] == "." and _e_abreviacao(texto, i):
            continue
        inicios.add(fim_espacos)
    return sorted(inicios)


def _primeiro_em(posicoes: List[int], minimo: int, maximo: int) -> int | None:
    """Menor posição em `posicoes` (ordenada) dentro de [minimo, maximo]."""
    k = bisect_left(posicoes, minimo)
    if k < len(posicoes) and posicoes[k] <= maximo:
        return posicoes[k]
    return None


def _ultimo_em(posicoes: List[int], minimo_excl: int, maximo: int) -> int | None:
    """Maior posição em `posicoes` (ordenada) dentro de (minimo_excl, maximo]."""
    k = bisect_right(posicoes, maximo) - 1
    if k >= 0 and posicoes[k] > minimo_excl:
        return posicoes[k]
    return None


class LegalChunker:
    """Segmentação de texto jurídico em blocos de ~`chunk_size` caracteres, com
    `overlap` caracteres de sobreposição e cortes em limites de frase.

    Fim do bloco: o último limite de frase em (inicio + L/2, inicio + L]; senão, o
    último início de palavra em (inicio, inicio + L]; senão (string sem espaços),
    corta em inicio + L. Os cortes caem sempre no início da frase/palavra seguinte,
    então o bloco pode terminar em espaço em branco e, sem sobreposição, o
    próximo bloco começa exatamente onde o anterior terminou.

    Próximo início: fim - overlap, avançado até o início da próxima frase (ou, na
    falta, da próxima palavra) dentro da região de sobreposição, e sempre
    estritamente maior que o início atual. Com overlap = 0, é o próprio fim.
    """

    def __init__(self, chunk_size: int = 3000, overlap: int = 600):
        if chunk_size <= 0:
            raise ValueError("chunk_size deve ser positivo.")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap deve estar no intervalo [0, chunk_size).")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, texto: str) -> List[LegalDocumentChunk]:
        if not texto.strip():
            return []

        n = len(texto)
        frases = _inicios_de_frase(texto)
        palavras = [m.start() for m in _INICIO_DE_PALAVRA.finditer(texto)]

        chunks: List[LegalDocumentChunk] = []
        inicio = 0
        while True:
            fim = self._fim_do_bloco(inicio, n, frases, palavras)
            fragmento = texto[inicio:fim]
            chunks.append(
                LegalDocumentChunk(
                    chunk_id=len(chunks),
                    texto=fragmento,
                    inicio_char=inicio,
                    fim_char=fim,
                    tamanho=len(fragmento),
                )
            )
            if fim >= n:
                return chunks
            inicio = self._proximo_inicio(inicio, fim, frases, palavras)

    def _fim_do_bloco(self, inicio: int, n: int, frases: List[int], palavras: List[int]) -> int:
        limite = inicio + self.chunk_size
        if limite >= n:
            return n
        corte = _ultimo_em(frases, inicio + self.chunk_size // 2, limite)
        if corte is None:
            corte = _ultimo_em(palavras, inicio, limite)
        return corte if corte is not None else limite

    def _proximo_inicio(self, inicio: int, fim: int, frases: List[int], palavras: List[int]) -> int:
        if self.overlap == 0:
            return fim
        alvo = max(fim - self.overlap, inicio + 1)
        # Limite superior exclusivo: começar em `fim` apagaria a sobreposição.
        prox = _primeiro_em(frases, alvo, fim - 1)
        if prox is None:
            prox = _primeiro_em(palavras, alvo, fim - 1)
        # Sem fronteira no trecho (palavra maior que a sobreposição): usa o alvo cru.
        return prox if prox is not None else alvo


def get_chunker(chunk_size: int | None = None, overlap: int | None = None) -> LegalChunker:
    """Fábrica do chunker. Sem argumentos, usa os defaults configurados via .env."""
    settings = get_settings()
    return LegalChunker(
        chunk_size=chunk_size or settings.chunk_size,
        overlap=overlap if overlap is not None else settings.chunk_overlap,
    )
