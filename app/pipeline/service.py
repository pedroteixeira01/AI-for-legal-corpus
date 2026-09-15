from app.anonymization.service import get_anonymizer
from app.chunking.service import get_chunker
from app.evaluation.service import get_evaluator
from app.pipeline.schemas import AnonimizacaoInfo, PipelineExecutionResult
from app.summarization.service import get_summarizer


def executar_pipeline(
    texto_original: str,
    referencia_humana: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> PipelineExecutionResult:
    """Orquestra o pipeline completo: sanitização (LGPD) -> chunking -> síntese -> avaliação ROUGE."""
    anonymizer = get_anonymizer()
    texto_limpo = anonymizer.sanitizar(texto_original)

    chunker = get_chunker(chunk_size=chunk_size, overlap=overlap)
    lista_chunks = chunker.chunk_text(texto_limpo)

    summarizer = get_summarizer()
    sumario_final = summarizer.sintetizar_chunks(lista_chunks)

    evaluator = get_evaluator()
    metricas = evaluator.calcular_metricas(sumario_final, referencia_humana)

    return PipelineExecutionResult(
        texto_original=texto_original,
        texto_anonimizado=texto_limpo,
        total_chunks=len(lista_chunks),
        chunks=lista_chunks,
        sumario_sintetizado=sumario_final,
        metricas_rouge=metricas,
        anonimizacao=AnonimizacaoInfo(modo=anonymizer.modo, ner_ativo=anonymizer.ner_ativo),
    )
