import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

import httpx

from app.chunking.schemas import LegalDocumentChunk
from app.core.config import get_settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Modelo usado no experimento (Llama 3.1 8B Instruct quantizado em Q4_K_M), no formato do `ramalama serve`.
MODELO_HF = "hf://bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"

# Fração de num_ctx a partir da qual a entrada é considerada no limite do contexto do servidor.
LIMIAR_TRUNCAMENTO = 0.95


class SummarizerError(RuntimeError):
    """Falha ao sintetizar (servidor fora do ar, contexto excedido, timeout, resposta inválida)."""


@dataclass
class ChamadaLLM:
    """Registro de uma chamada ao LLM (map ou reduce)."""

    etapa: str  # "map" ou "reduce"
    indice: int  # posição do bloco no map; 0 no reduce
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duracao_s: float | None = None  # tempo de parede da chamada HTTP
    finish_reason: str | None = None  # "stop", ou "length" se a saída bateu em LLM_NUM_PREDICT
    truncamento_suspeito: bool = False


@dataclass
class ResultadoSintese:
    """Síntese final junto com os metadados da execução."""

    texto: str
    extracoes_parciais: List[str] = field(default_factory=list)
    chamadas: List[ChamadaLLM] = field(default_factory=list)
    tempo_s: float = 0.0

    @property
    def truncamento_suspeito(self) -> bool:
        return any(c.truncamento_suspeito for c in self.chamadas)

    @property
    def tokens_prompt(self) -> int | None:
        valores = [c.prompt_tokens for c in self.chamadas if c.prompt_tokens is not None]
        return sum(valores) if valores else None

    @property
    def tokens_gerados(self) -> int | None:
        valores = [c.completion_tokens for c in self.chamadas if c.completion_tokens is not None]
        return sum(valores) if valores else None


class BaseSummarizer(ABC):
    """Interface para motores de síntese de corpus jurídico.

    Implementações: MockSummarizer (texto fixo, usado nos testes) e
    RamalamaSummarizer (map-reduce com um LLM local). Novos backends só precisam
    implementar este contrato, sem mudanças no restante do pipeline.
    """

    model_name: str

    @abstractmethod
    def sintetizar_chunks(self, chunks: List[LegalDocumentChunk]) -> str:
        raise NotImplementedError

    def parametros_do_modelo(self) -> dict:
        """Identificação do modelo que de fato responde, para registrar nos resultados."""
        return {"modelo": self.model_name}

    def parametros_de_geracao(self) -> dict:
        """Parâmetros de geração e versão dos prompts, para registrar nos resultados (a seed
        varia por execução e é registrada à parte)."""
        settings = get_settings()
        return {"temperature": settings.llm_temperature, "max_tokens": settings.llm_num_predict, **hash_prompts()}

    def sintetizar_com_metadados(self, chunks: List[LegalDocumentChunk], seed: int | None = None) -> ResultadoSintese:
        """Como `sintetizar_chunks`, mas devolve também extrações parciais, contagens
        de tokens e tempos. A implementação padrão não tem metadados a reportar."""
        inicio = time.perf_counter()
        texto = self.sintetizar_chunks(chunks)
        return ResultadoSintese(texto=texto, tempo_s=time.perf_counter() - inicio)


class MockSummarizer(BaseSummarizer):
    """Síntese fixa, sem LLM: não lê os chunks. Serve para testes e para validar o
    fluxo do pipeline sem um servidor LLM."""

    def __init__(self, model_name: str = "mock"):
        self.model_name = model_name

    def sintetizar_chunks(self, chunks: List[LegalDocumentChunk]) -> str:
        return (
            "SÍNTESE EXECUTIVA DO ACÓRDÃO JURÍDICO:\n"
            "1. TESE PRINCIPAL: Reconhecimento da responsabilidade civil objetiva por falha no serviço bancário, "
            "com base na aplicação do Código de Defesa do Consumidor e na Súmula 479 do STJ.\n"
            "2. DANOS MORAIS E MATERIAL: Mantida a condenação por danos morais fixada em R$ 10.000,00, "
            "e restituição em dobro dos valores indevidamente descontados.\n"
            "3. DISPOSITIVO: Recurso de apelação interposto pelo réu conhecido e desprovido por unanimidade de votos."
        )


# Alias de compatibilidade com o nome antigo.
LegalSummarizerLLM = MockSummarizer


def hash_prompts() -> dict:
    """SHA-256 dos arquivos de prompt versionados, para registrar com qual versão cada execução rodou."""
    return {
        f"prompt_{nome}_sha256": hashlib.sha256((PROMPTS_DIR / f"{nome}.txt").read_bytes()).hexdigest()
        for nome in ("map", "reduce")
    }


def carregar_prompt(nome: str) -> str:
    """Lê `prompts/<nome>.txt` em tempo de execução."""
    return (PROMPTS_DIR / f"{nome}.txt").read_text(encoding="utf-8").strip()


class RamalamaSummarizer(BaseSummarizer):
    """Síntese map-reduce com um LLM local servido pelo ramalama (llama.cpp), via a API
    compatível com OpenAI: `POST {RAMALAMA_URL}/v1/chat/completions`.

    Map: uma chamada por bloco extrai tese, fundamentos, valores e dispositivo.
    Reduce: uma chamada combina as extrações numeradas em uma síntese final.
    Mesmo com um único bloco, map + reduce são executados, para que todas as
    configurações do experimento usem exatamente os mesmos prompts.

    O tamanho do contexto é definido no servidor (`ramalama serve --ctx-size N`), não por
    requisição: `num_ctx` aqui só alimenta a detecção de truncamento e deve ser igual a N.
    """

    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        seed: int | None = None,
        num_predict: int | None = None,
        num_ctx: int | None = None,
        timeout_s: float | None = None,
        client: httpx.Client | None = None,
    ):
        settings = get_settings()
        self.url = (url or settings.ramalama_url).rstrip("/")
        self.model_name = model or settings.ramalama_model
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.seed = settings.llm_seed if seed is None else seed
        self.num_predict = num_predict or settings.llm_num_predict
        self.num_ctx = num_ctx or settings.llm_num_ctx
        self.timeout_s = timeout_s or settings.llm_timeout_s
        self._client = client or httpx.Client(timeout=self.timeout_s)
        self.info_servidor: dict = {}  # preenchido por verificar_disponibilidade()
        self._prompt_map = carregar_prompt("map")
        self._prompt_reduce = carregar_prompt("reduce")

    # -- interface pública -------------------------------------------------

    def sintetizar_chunks(self, chunks: List[LegalDocumentChunk]) -> str:
        return self.sintetizar_com_metadados(chunks).texto

    def sintetizar_com_metadados(self, chunks: List[LegalDocumentChunk], seed: int | None = None) -> ResultadoSintese:
        if not chunks:
            raise SummarizerError("Nenhum bloco para sintetizar.")
        seed = self.seed if seed is None else seed
        inicio = time.perf_counter()
        chamadas: List[ChamadaLLM] = []

        extracoes: List[str] = []
        for i, chunk in enumerate(chunks):
            prompt = self._prompt_map.replace("{trecho}", chunk.texto.strip())
            texto, chamada = self._gerar(prompt, seed, etapa="map", indice=i)
            extracoes.append(texto)
            chamadas.append(chamada)

        parciais = "\n\n".join(f"[Extração {i}]\n{e}" for i, e in enumerate(extracoes, start=1))
        prompt = self._prompt_reduce.replace("{parciais}", parciais)
        sintese, chamada = self._gerar(prompt, seed, etapa="reduce", indice=0)
        chamadas.append(chamada)

        return ResultadoSintese(
            texto=sintese,
            extracoes_parciais=extracoes,
            chamadas=chamadas,
            tempo_s=time.perf_counter() - inicio,
        )

    def verificar_disponibilidade(self) -> dict:
        """Falha com mensagem clara se o servidor não responde e devolve (e guarda em
        `info_servidor`) o que ele diz estar servindo.

        `RAMALAMA_MODEL` é só o nome enviado nas requisições (o llama.cpp o ignora): o
        modelo real, o arquivo GGUF (que revela a quantização), o build e o contexto vêm de
        `/v1/models` e `/props`. Avisa se o contexto difere de LLM_NUM_CTX ou se o modelo
        não parece o Llama 3.1 8B Instruct."""
        try:
            resposta = self._client.get(f"{self.url}/v1/models")
            resposta.raise_for_status()
            modelos = resposta.json()
        except httpx.TransportError as exc:
            raise self._erro_conexao(exc) from exc
        except httpx.HTTPStatusError as exc:
            raise SummarizerError(f"O servidor respondeu {exc.response.status_code} em {self.url}/v1/models.") from exc
        except ValueError as exc:
            raise SummarizerError(f"Resposta inesperada de {self.url}/v1/models: {resposta.text[:200]}") from exc

        props: dict = {}
        try:
            r = self._client.get(f"{self.url}/props")
            if r.status_code == 200:
                props = r.json()
        except (httpx.HTTPError, ValueError):
            pass  # /props é específico do llama.cpp: sem ele, só há o nome do modelo

        servido = _primeiro_nome(modelos) or props.get("model_alias")
        caminho = props.get("model_path")
        n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx")
        self.info_servidor = {
            "modelo": servido or self.model_name,
            "modelo_arquivo": Path(caminho).name if caminho else None,
            "servidor_build": props.get("build_info"),
            "n_ctx_servidor": n_ctx,
        }

        if n_ctx is not None and n_ctx != self.num_ctx:
            logger.warning(
                "O servidor reporta n_ctx=%s, mas LLM_NUM_CTX=%s: a detecção de truncamento usa LLM_NUM_CTX. "
                "Reinicie com `ramalama serve --ctx-size %s` ou ajuste LLM_NUM_CTX (com mais de um slot paralelo, "
                "o n_ctx por slot pode ser menor que o contexto total).",
                n_ctx,
                self.num_ctx,
                self.num_ctx,
            )
        if not _parece_llama31_8b_instruct(servido, self.info_servidor["modelo_arquivo"]):
            logger.warning(
                "O servidor serve '%s' (arquivo: %s), que não parece o Llama 3.1 8B Instruct do experimento.",
                servido,
                self.info_servidor["modelo_arquivo"],
            )
        return self.info_servidor

    def parametros_de_geracao(self) -> dict:
        return {"temperature": self.temperature, "max_tokens": self.num_predict, **hash_prompts()}

    def parametros_do_modelo(self) -> dict:
        """Modelo que de fato responde (após verificar_disponibilidade); do contrário, só o nome configurado."""
        return {"modelo": self.model_name, **{k: v for k, v in self.info_servidor.items() if v is not None}}

    # -- internos ------------------------------------------------------------

    def _gerar(self, prompt: str, seed: int, etapa: str, indice: int) -> tuple[str, ChamadaLLM]:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": self.temperature,
            "seed": seed,
            "max_tokens": self.num_predict,
            # Extensão do llama.cpp (ignorada por outros servidores): sem reaproveitar o cache
            # de prefixo, a contagem de tokens e a saída não dependem da chamada anterior.
            "cache_prompt": False,
        }
        inicio = time.perf_counter()
        try:
            resposta = self._client.post(f"{self.url}/v1/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise SummarizerError(
                f"Timeout de {self.timeout_s:g}s na chamada '{etapa}' ao servidor. "
                "Aumente LLM_TIMEOUT_S ou reduza o tamanho dos blocos."
            ) from exc
        except httpx.TransportError as exc:
            raise self._erro_conexao(exc) from exc
        duracao = time.perf_counter() - inicio

        if resposta.status_code == 400 and "context" in resposta.text.lower():
            raise SummarizerError(
                f"O prompt da chamada '{etapa}' excede o contexto do servidor ({resposta.text[:200]}). "
                "Reinicie o `ramalama serve` com --ctx-size maior (e ajuste LLM_NUM_CTX) ou reduza CHUNK_SIZE."
            )
        if resposta.status_code != 200:
            raise SummarizerError(f"O servidor respondeu {resposta.status_code}: {resposta.text[:300]}")

        try:
            dados = resposta.json()
            escolha = dados["choices"][0]
            texto = escolha["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise SummarizerError(f"Resposta inesperada do servidor: {resposta.text[:300]}") from exc
        uso = dados.get("usage") or {}

        chamada = ChamadaLLM(
            etapa=etapa,
            indice=indice,
            prompt_tokens=uso.get("prompt_tokens"),
            completion_tokens=uso.get("completion_tokens"),
            duracao_s=round(duracao, 3),
            finish_reason=escolha.get("finish_reason"),
        )
        if chamada.prompt_tokens is not None and chamada.prompt_tokens >= LIMIAR_TRUNCAMENTO * self.num_ctx:
            chamada.truncamento_suspeito = True
            logger.warning(
                "TRUNCAMENTO SUSPEITO na chamada '%s' (índice %d): prompt_tokens=%d >= %d%% de num_ctx=%d. "
                "A entrada está no limite do contexto do servidor; aumente --ctx-size (e LLM_NUM_CTX) ou reduza CHUNK_SIZE.",
                etapa,
                indice,
                chamada.prompt_tokens,
                round(LIMIAR_TRUNCAMENTO * 100),
                self.num_ctx,
            )
        if chamada.finish_reason == "length":
            logger.warning(
                "A saída da chamada '%s' (índice %d) foi cortada em LLM_NUM_PREDICT=%d tokens.",
                etapa,
                indice,
                self.num_predict,
            )
        return (texto or "").strip(), chamada

    def _erro_conexao(self, exc: Exception) -> SummarizerError:
        return SummarizerError(
            f"Não foi possível conectar ao servidor em {self.url} ({exc.__class__.__name__}). "
            f"Verifique se ele está rodando (`ramalama serve --ctx-size {self.num_ctx} {MODELO_HF}`) "
            "e se RAMALAMA_URL está correto."
        )


def _primeiro_nome(modelos: dict) -> str | None:
    """Nome do primeiro modelo listado em `/v1/models` (formatos OpenAI `data` ou llama.cpp `models`)."""
    try:
        return modelos["data"][0]["id"]
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return modelos["models"][0]["name"]
    except (KeyError, IndexError, TypeError):
        return None


def _parece_llama31_8b_instruct(*nomes: str | None) -> bool:
    """Heurística sobre o nome do modelo/arquivo: Llama 3.1, 8B, e variante Instruct
    (a tag `llama3.1:8b` do registro Ollama já é a Instruct, mesmo sem a palavra)."""
    normalizados = ["".join(c for c in n.lower() if c.isalnum()) for n in nomes if n]
    texto = " ".join(normalizados)
    return "llama31" in texto and "8b" in texto and ("instruct" in texto or "llama318b" in normalizados)


def criar_summarizer(backend: str | None = None) -> BaseSummarizer:
    """Instancia o summarizer do backend pedido (padrão: SUMMARIZER_BACKEND)."""
    backend = backend or get_settings().summarizer_backend
    if backend == "mock":
        return MockSummarizer()
    if backend == "ramalama":
        return RamalamaSummarizer()
    raise ValueError(f"Backend de síntese desconhecido: '{backend}' (use 'mock' ou 'ramalama').")


@lru_cache
def get_summarizer() -> BaseSummarizer:
    return criar_summarizer()
