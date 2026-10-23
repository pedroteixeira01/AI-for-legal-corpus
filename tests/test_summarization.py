"""Testes do RamalamaSummarizer com httpx.MockTransport: nenhuma chamada de rede é feita."""

import json

import httpx
import pytest

from app.chunking.schemas import LegalDocumentChunk
from app.summarization.service import (
    LegalSummarizerLLM,
    MockSummarizer,
    RamalamaSummarizer,
    SummarizerError,
    carregar_prompt,
    criar_summarizer,
)


def _chunk(i: int, texto: str) -> LegalDocumentChunk:
    return LegalDocumentChunk(chunk_id=i, texto=texto, inicio_char=0, fim_char=len(texto), tamanho=len(texto))


class ServidorFalso:
    """Servidor compatível com OpenAI simulado: registra as requisições e responde de forma determinística."""

    def __init__(self, prompt_tokens=100, n_ctx=None, finish_reason="stop", modelo="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
                 arquivo="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"):  # fmt: skip
        self.requisicoes: list[dict] = []
        self.prompt_tokens = prompt_tokens
        self.n_ctx = n_ctx
        self.finish_reason = finish_reason
        self.modelo = modelo
        self.arquivo = arquivo

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [{"name": self.modelo}], "data": [{"id": self.modelo}]})
        if request.url.path == "/props":
            if self.n_ctx is None:
                return httpx.Response(404)
            return httpx.Response(
                200,
                json={
                    "default_generation_settings": {"n_ctx": self.n_ctx},
                    "model_path": f"/mnt/models/{self.arquivo}",
                    "build_info": "b1-b29c606",
                },
            )
        assert request.url.path == "/v1/chat/completions"
        corpo = json.loads(request.content)
        self.requisicoes.append(corpo)
        n = len(self.requisicoes)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": f"  resposta {n}  "}, "finish_reason": self.finish_reason}],
                "usage": {"prompt_tokens": self.prompt_tokens, "completion_tokens": 10 * n},
            },
        )


def _summarizer(handler, **kwargs) -> RamalamaSummarizer:
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    return RamalamaSummarizer(url="http://servidor.teste", model="llama3.1:8b", client=cliente, **kwargs)


def test_map_reduce_faz_uma_chamada_por_bloco_mais_o_reduce():
    servidor = ServidorFalso()
    s = _summarizer(servidor, temperature=0.1, seed=42, num_predict=512, num_ctx=16384)

    resultado = s.sintetizar_com_metadados([_chunk(0, "Trecho A."), _chunk(1, "Trecho B."), _chunk(2, "Trecho C.")])

    assert len(servidor.requisicoes) == 4
    assert resultado.extracoes_parciais == ["resposta 1", "resposta 2", "resposta 3"]
    assert resultado.texto == "resposta 4"
    assert [c.etapa for c in resultado.chamadas] == ["map", "map", "map", "reduce"]
    assert resultado.tokens_prompt == 400
    assert resultado.tokens_gerados == 10 + 20 + 30 + 40
    assert all(c.duracao_s is not None and c.finish_reason == "stop" for c in resultado.chamadas)
    assert not resultado.truncamento_suspeito


def test_payload_segue_o_contrato_openai():
    servidor = ServidorFalso()
    s = _summarizer(servidor, temperature=0.1, seed=42, num_predict=512, num_ctx=16384)

    s.sintetizar_com_metadados([_chunk(0, "Trecho A.")], seed=43)

    for req in servidor.requisicoes:
        assert req["model"] == "llama3.1:8b"
        assert req["stream"] is False
        assert (req["temperature"], req["seed"], req["max_tokens"]) == (0.1, 43, 512)
        assert req["cache_prompt"] is False
        assert [m["role"] for m in req["messages"]] == ["user"]


def test_bloco_unico_ainda_faz_map_e_reduce_com_os_mesmos_prompts():
    servidor = ServidorFalso()
    s = _summarizer(servidor)

    resultado = s.sintetizar_com_metadados([_chunk(0, "Documento inteiro.")])

    assert len(servidor.requisicoes) == 2
    assert "Documento inteiro." in servidor.requisicoes[0]["messages"][0]["content"]
    assert servidor.requisicoes[0]["messages"][0]["content"].startswith(carregar_prompt("map").split("{trecho}")[0])
    assert servidor.requisicoes[1]["messages"][0]["content"].startswith(carregar_prompt("reduce").split("{parciais}")[0])
    assert resultado.extracoes_parciais == ["resposta 1"]


def test_reduce_recebe_as_extracoes_numeradas_e_em_ordem():
    servidor = ServidorFalso()
    s = _summarizer(servidor)

    s.sintetizar_com_metadados([_chunk(0, "A."), _chunk(1, "B.")])

    prompt_reduce = servidor.requisicoes[-1]["messages"][0]["content"]
    assert prompt_reduce.index("[Extração 1]\nresposta 1") < prompt_reduce.index("[Extração 2]\nresposta 2")


def test_trecho_com_chaves_nao_quebra_o_prompt():
    servidor = ServidorFalso()
    s = _summarizer(servidor)

    s.sintetizar_com_metadados([_chunk(0, "Cláusula {parciais} e {trecho} literais.")])

    assert "Cláusula {parciais} e {trecho} literais." in servidor.requisicoes[0]["messages"][0]["content"]


def test_truncamento_suspeito_e_sinalizado_com_aviso(caplog):
    servidor = ServidorFalso(prompt_tokens=950)
    s = _summarizer(servidor, num_ctx=1000)

    with caplog.at_level("WARNING"):
        resultado = s.sintetizar_com_metadados([_chunk(0, "Trecho.")])

    assert resultado.truncamento_suspeito
    assert all(c.truncamento_suspeito for c in resultado.chamadas)
    assert "TRUNCAMENTO SUSPEITO" in caplog.text


def test_abaixo_do_limiar_nao_sinaliza_truncamento():
    servidor = ServidorFalso(prompt_tokens=949)
    s = _summarizer(servidor, num_ctx=1000)

    assert not s.sintetizar_com_metadados([_chunk(0, "Trecho.")]).truncamento_suspeito


def test_servidor_fora_do_ar_gera_mensagem_clara():
    def recusa(request):
        raise httpx.ConnectError("conexão recusada")

    with pytest.raises(SummarizerError, match="ramalama serve"):
        _summarizer(recusa).sintetizar_chunks([_chunk(0, "x")])


def test_contexto_excedido_gera_mensagem_clara():
    def estourou(request):
        return httpx.Response(400, json={"error": {"type": "exceed_context_size_error", "message": "the request exceeds the available context size"}})

    with pytest.raises(SummarizerError, match="--ctx-size"):
        _summarizer(estourou).sintetizar_chunks([_chunk(0, "x")])


def test_resposta_fora_do_formato_gera_erro():
    with pytest.raises(SummarizerError, match="inesperada"):
        _summarizer(lambda r: httpx.Response(200, json={"foo": "bar"})).sintetizar_chunks([_chunk(0, "x")])


def test_timeout_gera_mensagem_clara():
    def lento(request):
        raise httpx.ReadTimeout("demorou")

    with pytest.raises(SummarizerError, match="LLM_TIMEOUT_S"):
        _summarizer(lento, timeout_s=5).sintetizar_chunks([_chunk(0, "x")])


def test_saida_cortada_em_num_predict_e_registrada(caplog):
    servidor = ServidorFalso(finish_reason="length")

    with caplog.at_level("WARNING"):
        resultado = _summarizer(servidor).sintetizar_com_metadados([_chunk(0, "x")])

    assert resultado.chamadas[-1].finish_reason == "length"
    assert "LLM_NUM_PREDICT" in caplog.text


def test_verificar_disponibilidade(caplog):
    _summarizer(ServidorFalso()).verificar_disponibilidade()  # /props ausente: tudo bem
    _summarizer(ServidorFalso(n_ctx=16384), num_ctx=16384).verificar_disponibilidade()
    assert "n_ctx" not in caplog.text

    with caplog.at_level("WARNING"):
        _summarizer(ServidorFalso(n_ctx=4096), num_ctx=16384).verificar_disponibilidade()
    assert "n_ctx=4096" in caplog.text

    def fora(request):
        raise httpx.ConnectError("recusada")

    with pytest.raises(SummarizerError, match="ramalama serve"):
        _summarizer(fora).verificar_disponibilidade()


def test_sem_blocos_levanta_erro():
    with pytest.raises(SummarizerError):
        _summarizer(ServidorFalso()).sintetizar_chunks([])


def test_mock_nao_le_os_chunks_e_alias_antigo_funciona():
    assert LegalSummarizerLLM is MockSummarizer
    assert MockSummarizer().sintetizar_chunks([]) == MockSummarizer().sintetizar_chunks([_chunk(0, "qualquer coisa")])


def test_mock_com_metadados_nao_tem_tokens():
    resultado = MockSummarizer().sintetizar_com_metadados([_chunk(0, "x")])

    assert resultado.texto
    assert resultado.tokens_prompt is None
    assert resultado.chamadas == []
    assert not resultado.truncamento_suspeito


def test_fabrica_respeita_o_backend_configurado(monkeypatch):
    from app.core.config import get_settings

    assert isinstance(criar_summarizer(), MockSummarizer)  # fixture autouse força "mock"
    assert isinstance(criar_summarizer("ramalama"), RamalamaSummarizer)

    monkeypatch.setenv("SUMMARIZER_BACKEND", "ramalama")
    get_settings.cache_clear()
    assert isinstance(criar_summarizer(), RamalamaSummarizer)

    with pytest.raises(ValueError):
        criar_summarizer("gpt")


def test_prompts_versionados_tem_os_marcadores():
    assert "{trecho}" in carregar_prompt("map")
    assert "{parciais}" in carregar_prompt("reduce")


def test_verificar_disponibilidade_registra_o_modelo_realmente_servido():
    s = _summarizer(ServidorFalso(n_ctx=16384), num_ctx=16384)

    info = s.verificar_disponibilidade()

    assert info == {
        "modelo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "modelo_arquivo": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "servidor_build": "b1-b29c606",
        "n_ctx_servidor": 16384,
    }
    # RAMALAMA_MODEL ("llama3.1:8b") é só o nome enviado nas requisições; o registrado é o servido.
    assert s.parametros_do_modelo() == {"modelo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", **{k: v for k, v in info.items() if k != "modelo"}}


def test_sem_verificar_o_modelo_registrado_e_o_configurado():
    assert _summarizer(ServidorFalso()).parametros_do_modelo() == {"modelo": "llama3.1:8b"}
    assert MockSummarizer().parametros_do_modelo() == {"modelo": "mock"}


def test_servidor_sem_props_ainda_identifica_o_modelo():
    info = _summarizer(ServidorFalso(n_ctx=None)).verificar_disponibilidade()

    assert info["modelo"] == "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
    assert info["modelo_arquivo"] is None and info["n_ctx_servidor"] is None


def test_aviso_quando_o_modelo_servido_nao_e_o_llama31_8b_instruct(caplog):
    with caplog.at_level("WARNING"):
        _summarizer(ServidorFalso(n_ctx=16384, modelo="outro/Qwen2.5-7B-Instruct-GGUF", arquivo="Qwen2.5-7B-Instruct-Q4_K_M.gguf"), num_ctx=16384).verificar_disponibilidade()

    assert "não parece o Llama 3.1 8B Instruct" in caplog.text


def test_sem_aviso_para_o_modelo_esperado(caplog):
    with caplog.at_level("WARNING"):
        _summarizer(ServidorFalso(n_ctx=16384), num_ctx=16384).verificar_disponibilidade()

    assert "não parece" not in caplog.text


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", True),
        ("llama3.1:8b", True),  # tag do registro Ollama: já é a Instruct
        ("meta-llama/Llama-3.1-8B-Instruct", True),
        ("Meta-Llama-3.1-8B", False),  # base, sem Instruct
        ("Meta-Llama-3.1-70B-Instruct", False),
        ("Meta-Llama-3-8B-Instruct", False),  # Llama 3, não 3.1
        ("qwen2.5:7b", False),
    ],
)
def test_heuristica_do_modelo_esperado(nome, esperado):
    from app.summarization.service import _parece_llama31_8b_instruct

    assert _parece_llama31_8b_instruct(nome) is esperado
