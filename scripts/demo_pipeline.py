"""Demonstração em linha de comando do pipeline completo, sem subir a API.

Reproduz exatamente o fluxo e as saídas do main.py original do protótipo:
sanitização (LGPD) -> chunking -> síntese (mock) -> avaliação ROUGE.

Uso:
    python scripts/demo_pipeline.py
"""

import sys
from pathlib import Path

# Permite rodar via `python scripts/demo_pipeline.py` a partir da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.anonymization.service import LGPDAnonymizer
from app.chunking.service import LegalChunker
from app.core.samples import CORPUS_JURIDICO_EXEMPLO, REFERENCIA_HUMANA_GOLD
from app.evaluation.service import EvaluatorROUGE
from app.pipeline.schemas import AnonimizacaoInfo, PipelineExecutionResult
from app.summarization.service import LegalSummarizerLLM


def main() -> None:
    print("#### INICIANDO PIPELINE DE PROCESSAMENTO DE CORPUS JURÍDICO ####")

    anonymizer = LGPDAnonymizer()
    if not anonymizer.ner_ativo:
        print(
            "\n[AVISO] Modelo spaCy não encontrado — rodando em modo degradado "
            "(somente regex). Rode: python -m spacy download pt_core_news_lg"
        )
    texto_limpo = anonymizer.sanitizar(CORPUS_JURIDICO_EXEMPLO)
    print(f"\n[1] Texto Sanitizado (LGPD - Privacy by Design Executado, modo={anonymizer.modo})")

    chunker = LegalChunker(chunk_size=350, overlap=80)
    lista_chunks = chunker.chunk_text(texto_limpo)
    print(f"\n[2] Chunking Concluído: {len(lista_chunks)} blocos gerados com sobreposição semântica.")
    for c in lista_chunks:
        print(f"   -> Chunk {c.chunk_id} | Tamanho: {c.tamanho} chars | Start: {c.inicio_char} End: {c.fim_char}")

    llm_engine = LegalSummarizerLLM()
    sumario_final = llm_engine.sintetizar_chunks(lista_chunks)
    print("\n[3] Síntese Gerada pelo Modelo:")
    print(sumario_final)

    evaluator = EvaluatorROUGE()
    metricas = evaluator.calcular_metricas(sumario_final, REFERENCIA_HUMANA_GOLD)
    print("\n[4] Métricas de Desempenho (ROUGE Score):")
    print(f"   - ROUGE-1 F1-Score: {metricas['rouge1']['fmeasure']}")
    print(f"   - ROUGE-2 F1-Score: {metricas['rouge2']['fmeasure']}")
    print(f"   - ROUGE-L F1-Score: {metricas['rougeL']['fmeasure']}")

    resultado_pipeline = PipelineExecutionResult(
        texto_original=CORPUS_JURIDICO_EXEMPLO,
        texto_anonimizado=texto_limpo,
        total_chunks=len(lista_chunks),
        chunks=lista_chunks,
        sumario_sintetizado=sumario_final,
        metricas_rouge=metricas,
        anonimizacao=AnonimizacaoInfo(modo=anonymizer.modo, ner_ativo=anonymizer.ner_ativo),
    )
    return resultado_pipeline


if __name__ == "__main__":
    main()
