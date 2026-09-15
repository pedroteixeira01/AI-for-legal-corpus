import logging
import re
from functools import lru_cache
from typing import List

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

from app.anonymization.schemas import EntidadeDetectada
from app.core.config import get_settings

logger = logging.getLogger(__name__)

ENTIDADES_LGPD = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "BR_CPF"]

# Regex complementar: cobre CPFs no padrão XXX.XXX.XXX-XX mesmo se o NER falhar
# em reconhecê-los como PII (camada determinística, sempre executada).
_REGEX_CPF_PONTUADO = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")


def _criar_recognizer_cpf() -> PatternRecognizer:
    """CPF não é uma entidade predefinida no Presidio — este recognizer a introduz
    no idioma 'pt', complementando (não substituindo) a regex de pós-processamento.
    """
    padroes = [
        Pattern(name="cpf_pontuado", regex=r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", score=0.8),
        Pattern(name="cpf_simples", regex=r"\b\d{11}\b", score=0.3),
    ]
    return PatternRecognizer(
        supported_entity="BR_CPF",
        supported_language="pt",
        patterns=padroes,
        context=["cpf", "cadastro de pessoa física", "inscrição"],
    )


class LGPDAnonymizer:
    """Anonimização de entidades sensíveis alinhada à LGPD e à Resolução CNJ nº 615/2025.

    Reaproveitado de main.py, corrigindo o bug de idioma: o Presidio era
    chamado com language="en" sobre texto em português (o que faz os
    recognizers padrão nunca casarem). Agora o AnalyzerEngine é montado
    explicitamente para 'pt', usando o modelo spaCy configurado.

    Se o modelo spaCy não estiver disponível, a instância degrada para um
    modo "regex_only": a API continua funcional, mas sem NER (apenas a
    camada de regex de CPF é aplicada). Isso é sinalizado via `ner_ativo`.
    """

    def __init__(self):
        settings = get_settings()
        self._idioma = settings.presidio_language
        self.analyzer: AnalyzerEngine | None = None
        self.anonymizer = AnonymizerEngine()
        self.ner_ativo = False

        try:
            provider = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": self._idioma, "model_name": settings.spacy_model}],
                }
            )
            nlp_engine = provider.create_engine()

            registry = RecognizerRegistry(supported_languages=[self._idioma])
            registry.load_predefined_recognizers(languages=[self._idioma], nlp_engine=nlp_engine)
            registry.add_recognizer(_criar_recognizer_cpf())

            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                registry=registry,
                supported_languages=[self._idioma],
            )
            self.ner_ativo = True
        except (OSError, ValueError) as exc:
            logger.warning(
                "Modelo spaCy '%s' não encontrado — anonimização em modo degradado "
                "(somente regex). Para ativar o NER completo, rode: "
                "python -m spacy download %s (detalhe: %s)",
                settings.spacy_model,
                settings.spacy_model,
                exc,
            )

    @property
    def modo(self) -> str:
        return "presidio_pt" if self.ner_ativo else "regex_only"

    def analisar(self, texto: str) -> List[EntidadeDetectada]:
        """Retorna as entidades sensíveis detectadas pelo Presidio, sem anonimizar."""
        if not self.ner_ativo or self.analyzer is None:
            return []
        resultados: List[RecognizerResult] = self.analyzer.analyze(
            text=texto,
            entities=ENTIDADES_LGPD,
            language=self._idioma,
        )
        return [
            EntidadeDetectada(tipo=r.entity_type, inicio=r.start, fim=r.end, score=round(r.score, 4))
            for r in resultados
        ]

    def sanitizar(self, texto: str) -> str:
        texto_anonimizado = texto

        if self.ner_ativo and self.analyzer is not None:
            resultados: List[RecognizerResult] = self.analyzer.analyze(
                text=texto,
                entities=ENTIDADES_LGPD,
                language=self._idioma,
            )
            texto_anonimizado = self.anonymizer.anonymize(
                text=texto_anonimizado,
                analyzer_results=resultados,
            ).text

        # Sanitização complementar via regras estritas (sempre executada,
        # mesmo em modo degradado): oculta CPFs no padrão XXX.XXX.XXX-XX
        texto_anonimizado = _REGEX_CPF_PONTUADO.sub("[CPF_OMITIDO]", texto_anonimizado)
        return texto_anonimizado


@lru_cache
def get_anonymizer() -> LGPDAnonymizer:
    """O AnalyzerEngine é caro de construir (carrega o modelo spaCy) —
    reutiliza uma única instância para toda a aplicação."""
    return LGPDAnonymizer()
