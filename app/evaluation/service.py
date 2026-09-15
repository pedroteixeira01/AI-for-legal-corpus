from functools import lru_cache

from rouge_score import rouge_scorer


class EvaluatorROUGE:
    """Avaliação quantitativa da síntese via métrica ROUGE.

    Reaproveitado de main.py sem alterações na lógica de negócio.
    """

    def __init__(self):
        self.scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)

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
