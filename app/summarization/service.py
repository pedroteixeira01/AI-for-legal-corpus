from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List

from app.chunking.schemas import LegalDocumentChunk
from app.core.config import get_settings


class BaseSummarizer(ABC):
    """Interface para motores de síntese de corpus jurídico.

    Ponto de extensão: uma implementação real (chamada a uma API de LLM —
    OpenAI, Anthropic, um modelo self-hosted via LangChain/LlamaIndex etc.)
    pode substituir LegalSummarizerLLM implementando este mesmo contrato,
    sem exigir mudanças no restante do pipeline (chunking, avaliação,
    orquestrador).
    """

    @abstractmethod
    def sintetizar_chunks(self, chunks: List[LegalDocumentChunk]) -> str:
        raise NotImplementedError


class LegalSummarizerLLM(BaseSummarizer):
    """Simula o comportamento de um LLM especializado (ex: Llama-3-70B / LEGAL-BERT / GPT-4o)
    processando o corpus chunk por chunk e aplicando fusão hierárquica de teses.

    Reaproveitado de main.py: implementação mock, retorna uma síntese fixa.
    Nenhuma chamada real a LLM é feita aqui — ver docstring de BaseSummarizer.
    """

    def __init__(self, model_name: str = "Meta-Llama-3-70B-Instruct-Legal"):
        self.model_name = model_name

    def sintetizar_chunks(self, chunks: List[LegalDocumentChunk]) -> str:
        # Em produção: invoca a API do LLM / LangChain / LlamaIndex para Map-Reduce ou Refine
        # Aqui geramos a síntese técnica resultante do processamento do corpus
        sumario = (
            "SÍNTESE EXECUTIVA DO ACÓRDÃO JURÍDICO:\n"
            "1. TESE PRINCIPAL: Reconhecimento da responsabilidade civil objetiva por falha no serviço bancário, "
            "com base na aplicação do Código de Defesa do Consumidor e na Súmula 479 do STJ.\n"
            "2. DANOS MORAIS E MATERIAL: Mantida a condenação por danos morais fixada em R$ 10.000,00, "
            "e restituição em dobro dos valores indevidamente descontados.\n"
            "3. DISPOSITIVO: Recurso de apelação interposto pelo réu conhecido e desprovido por unanimidade de votos."
        )
        return sumario


@lru_cache
def get_summarizer() -> BaseSummarizer:
    settings = get_settings()
    return LegalSummarizerLLM(model_name=settings.summarizer_model_name)
