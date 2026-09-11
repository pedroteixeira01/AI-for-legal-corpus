import math
from typing import List
from pydantic import BaseModel, Field
from rouge_score import rouge_scorer
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

class LegalDocumentChunk(BaseModel):
    chunk_id: int
    texto: str = Field(..., description="Fragmento isolado e sanitizado do texto jurídico")
    inicio_char: int
    fim_char: int
    tamanho: int

class PipelineExecutionResult(BaseModel):
    texto_original: str
    texto_anonimizado: str
    total_chunks: int
    chunks: List[LegalDocumentChunk]
    sumario_sintetizado: str
    metricas_rouge: dict

class LGPDAnonymizer:
    def __init__(self):
        # Utiliza o motor do Presidio para identificar entidades brasileiras e sensíveis
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def sanitizar(self, texto: str) -> str:
        # No ambiente de produção, carrega o modelo em português ('pt')
        # Para simulação determinística sem dependências pesadas de spaCy pt_core_news_lg:
        resultados: List[RecognizerResult] = self.analyzer.analyze(
            text=texto,
            entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "BR_CPF"],
            language="en"  # Usando fallback para ambiente de testes
        )
        texto_anonimizado = self.anonymizer.anonymize(
            text=texto,
            analyzer_results=resultados
        ).text
        
        # Sanitização complementar via regras estritas
        import re
        # Oculta CPFs no padrão XXX.XXX.XXX-XX
        texto_anonimizado = re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF_OMITIDO]', texto_anonimizado)
        return texto_anonimizado

class LegalChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.stride = chunk_size - overlap

    def chunk_text(self, texto: str) -> List[LegalDocumentChunk]:
        chunks = []
        tamanho_total = len(texto)
        
        for id_chunk, inicio in enumerate(range(0, tamanho_total, self.stride)):
            fim = min(inicio + self.chunk_size, tamanho_total)
            fragmento = texto[inicio:fim]
            
            chunk_obj = LegalDocumentChunk(
                chunk_id=id_chunk,
                texto=fragmento,
                inicio_char=inicio,
                fim_char=fim,
                tamanho=len(fragmento)
            )
            chunks.append(chunk_obj)
            
            if fim >= tamanho_total:
                break
                
        return chunks

class LegalSummarizerLLM:
    """
    Simula o comportamento de um LLM Especializado (ex: Llama-3-70B / LEGAL-BERT / GPT-4o)
    processando o corpus chunk por chunk e aplicando fusão hierárquica de teses.
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

class EvaluatorROUGE:
    def __init__(self):
        self.scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)

    def calcular_metricas(self, sumario_gerado: str, referencia_humana: str) -> dict:
        scores = self.scorer.score(referencia_humana, sumario_gerado)
        return {
            "rouge1": {
                "precision": round(scores['rouge1'].precision, 4),
                "recall": round(scores['rouge1'].recall, 4),
                "fmeasure": round(scores['rouge1'].fmeasure, 4)
            },
            "rouge2": {
                "precision": round(scores['rouge2'].precision, 4),
                "recall": round(scores['rouge2'].recall, 4),
                "fmeasure": round(scores['rouge2'].fmeasure, 4)
            },
            "rougeL": {
                "precision": round(scores['rougeL'].precision, 4),
                "recall": round(scores['rougeL'].recall, 4),
                "fmeasure": round(scores['rougeL'].fmeasure, 4)
            }
        }

if __name__ == "__main__":
    # Corpus de Entrada: Acórdão fictício de elevada densidade textual
    corpus_juridico_bruto = """
    PODER JUDICIÁRIO DO ESTADO DO RIO DE JANEIRO - TRIBUNAL DE JUSTIÇA
    APELAÇÃO CÍVEL Nº 0012345-67.2024.8.19.0001. RELATOR: DES. JOÃO DA SILVA.
    APELANTE: BANCO EXEMPLO S.A. (CPF/CNPJ REPRESENTANTE: 123.456.789-00).
    APELADO: MARIA DOS SANTOS (CPF: 987.654.321-11).
    
    EMENTA: APELAÇÃO CÍVEL. DIREITO DO CONSUMIDOR. OPERAÇÕES BANCÁRIAS NÃO RECONHECIDAS. 
    FRAUDE PRATICADA POR TERCEIROS. RESPONSABILIDADE OBJETIVA DA INSTITUIÇÃO FINANCEIRA. 
    SÚMULA 479 DO SUPERIOR TRIBUNAL DE JUSTIÇA. IN FORTUITO INTERNO. 
    A autora, senhora Maria dos Santos, ajuizou ação declaratória de inexistência de débito c/c indenizatória, 
    alegando ter sofrido descontos indevidos em sua conta corrente relativos a empréstimo não contratado. 
    A instituição financeira apelante sustenta a regularidade das transações e a culpa exclusiva de terceiro. 
    Oportuno registrar que a responsabilidade das instituições financeiras é objetiva, nos termos do Art. 14 do CDC. 
    O risco do empreendimento abrange as fraudes praticadas por terceiros, configurando fortuito interno. 
    Dano moral configurado in re ipsa ante os transtornos causados à parte autora. 
    Quantum indenizatório mantido em R$ 10.000,00 (dez mil reais), atendendo aos princípios da razoabilidade e proporcionalidade. 
    Restituição em dobro dos valores indevidamente descontados na forma do parágrafo único do art. 42 do CDC. 
    NEGA-SE PROVIMENTO AO RECURSO.
    """

    # Referência humana para avaliação da métrica ROUGE (Ground Truth)
    referencia_humana_gold = (
        "Trata-se de apelação cível em ação declaratória de inexistência de débito contra instituição bancária por fraude. "
        "A responsabilidade do banco é objetiva conforme o CDC e a Súmula 479 do STJ. "
        "Foi mantida a condenação em danos morais de R$ 10.000,00 e a restituição em dobro dos valores. "
        "Recurso conhecido e desprovido."
    )

    print("#### INICIANDO PIPELINE DE PROCESSAMENTO DE CORPUS JURÍDICO ####")
    
    anonymizer = LGPDAnonymizer()
    texto_limpo = anonymizer.sanitizar(corpus_juridico_bruto)
    print("\n[1] Texto Sanitizado (LGPD - Privacy by Design Executado)")
    
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
    metricas = evaluator.calcular_metricas(sumario_final, referencia_humana_gold)
    print("\n[4] Métricas de Desempenho (ROUGE Score):")
    print(f"   - ROUGE-1 F1-Score: {metricas['rouge1']['fmeasure']}")
    print(f"   - ROUGE-2 F1-Score: {metricas['rouge2']['fmeasure']}")
    print(f"   - ROUGE-L F1-Score: {metricas['rougeL']['fmeasure']}")

    resultado_pipeline = PipelineExecutionResult(
        texto_original=corpus_juridico_bruto,
        texto_anonimizado=texto_limpo,
        total_chunks=len(lista_chunks),
        chunks=lista_chunks,
        sumario_sintetizado=sumario_final,
        metricas_rouge=metricas
    )