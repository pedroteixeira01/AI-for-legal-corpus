import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from rouge_score import rouge_scorer


class TokenizadorUnicode:
    """Tokenizador do ROUGE que preserva acentos: minúsculas + `\\w+` (Unicode).

    O tokenizador padrão do `rouge-score` troca por espaço tudo que não é
    [a-z0-9], descartando letras acentuadas ("apelação" vira "apela", "o").
    """

    def tokenize(self, texto: str) -> List[str]:
        return re.findall(r"\w+", texto.lower())


class EvaluatorROUGE:
    """Avaliação quantitativa da síntese via métrica ROUGE (sem stemmer)."""

    def __init__(self):
        self.scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], tokenizer=TokenizadorUnicode())

    def calcular_metricas(self, sumario_gerado: str, referencia_humana: str) -> dict:
        scores = self.scorer.score(referencia_humana, sumario_gerado)
        return {
            "rouge1": {
                "precision": round(scores["rouge1"].precision, 4),
                "recall": round(scores["rouge1"].recall, 4),
                "fmeasure": round(scores["rouge1"].fmeasure, 4),
            },
            "rouge2": {
                "precision": round(scores["rouge2"].precision, 4),
                "recall": round(scores["rouge2"].recall, 4),
                "fmeasure": round(scores["rouge2"].fmeasure, 4),
            },
            "rougeL": {
                "precision": round(scores["rougeL"].precision, 4),
                "recall": round(scores["rougeL"].recall, 4),
                "fmeasure": round(scores["rougeL"].fmeasure, 4),
            },
        }


@lru_cache
def get_evaluator() -> EvaluatorROUGE:
    return EvaluatorROUGE()


def normalizar_para_checklist(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços colapsados."""
    sem_acentos = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sem_acentos.lower()).strip()


def avaliar_checklist(sintese: str, checklist: Dict[str, List[str]]) -> dict:
    """Verifica quais itens do checklist factual aparecem na síntese.

    `checklist` mapeia cada item às suas variantes aceitas; o item é atendido se
    qualquer variante aparecer na síntese (após normalização de ambos os lados).
    Retorna `{"itens": {item: bool}, "proporcao": fração de itens atendidos}`.
    """
    texto = normalizar_para_checklist(sintese)
    itens = {
        item: any(normalizar_para_checklist(v) in texto for v in variantes if v.strip())
        for item, variantes in checklist.items()
    }
    proporcao = sum(itens.values()) / len(itens) if itens else 0.0
    return {"itens": itens, "proporcao": round(proporcao, 4)}


def carregar_checklist(caminho: Path) -> Dict[str, List[str]]:
    """Lê um `checklist.json` ({item: [variantes]}) validando o formato."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(dados, dict) or not dados or not all(
        isinstance(v, list) and v and all(isinstance(x, str) for x in v) for v in dados.values()
    ):
        raise ValueError(f"{caminho}: esperado um objeto {{item: [variantes não vazias, em texto]}}.")
    return dados
