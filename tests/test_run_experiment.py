"""Testes do script de experimento: backend mock e servidor LLM simulado (sem rede)."""

import importlib.util
import json
import shutil
from pathlib import Path

import httpx
import pytest

from app.summarization.service import RamalamaSummarizer

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "data" / "experimento" / "exemplo_ficticio"


@pytest.fixture(scope="module")
def exp():
    spec = importlib.util.spec_from_file_location("run_experiment", RAIZ / "scripts" / "run_experiment.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def dados(tmp_path):
    pasta = tmp_path / "dados"
    shutil.copytree(EXEMPLO, pasta / "doc_a")
    return pasta


def _rodar(exp, dados, resultados, *extra):
    return exp.main(["--backend", "mock", "--data-dir", str(dados), "--out", str(resultados), *extra])


def test_fluxo_mock_gera_raw_csv_e_markdown(exp, dados, tmp_path):
    resultados = tmp_path / "res"

    assert _rodar(exp, dados, resultados, "--runs", "2") == 0

    linhas = [json.loads(l) for l in (resultados / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(linhas) == 3 * 2  # 3 configurações x 2 repetições
    assert {l["seed"] for l in linhas} == {42, 43}
    assert {l["configuracao"] for l in linhas} == {"inteiro", "blocos_sem_sobreposicao", "blocos_com_sobreposicao"}
    blocos = {l["configuracao"]: l["n_blocos"] for l in linhas}
    assert blocos["inteiro"] == 1 and blocos["blocos_sem_sobreposicao"] >= 3
    assert blocos["blocos_com_sobreposicao"] >= blocos["blocos_sem_sobreposicao"]
    campos = {"sintese", "extracoes_parciais", "rouge", "checklist", "tokens", "tempo_s", "truncamento_suspeito"}
    assert campos <= set(linhas[0])
    assert set(linhas[0]["rouge"]["rouge1"]) == {"precision", "recall", "fmeasure"}

    assert (resultados / "summary.csv").read_text(encoding="utf-8").startswith("doc_id,configuracao")
    md = (resultados / "summary.md").read_text(encoding="utf-8")
    assert "EXECUÇÃO DE TESTE" in md
    assert md.count("## ") == 3
    assert "TJRJ (fictício)" in md


def test_resume_pula_execucoes_existentes(exp, dados, tmp_path, capsys):
    resultados = tmp_path / "res"
    assert _rodar(exp, dados, resultados, "--runs", "1") == 0
    antes = (resultados / "raw.jsonl").read_text(encoding="utf-8")

    assert _rodar(exp, dados, resultados, "--runs", "2", "--resume") == 0

    linhas = (resultados / "raw.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 6
    assert "\n".join(linhas[:3]) + "\n" == antes
    assert capsys.readouterr().out.count("já existe, pulando") == 3


def test_raw_existente_sem_resume_aborta(exp, dados, tmp_path, capsys):
    resultados = tmp_path / "res"
    assert _rodar(exp, dados, resultados, "--runs", "1") == 0

    assert _rodar(exp, dados, resultados, "--runs", "1") == 1

    assert "--resume" in capsys.readouterr().err
    assert len((resultados / "raw.jsonl").read_text(encoding="utf-8").splitlines()) == 3  # nada foi sobrescrito


def test_documento_curto_aborta_antes_do_lote(exp, dados, tmp_path, capsys):
    curto = dados / "curto"
    shutil.copytree(EXEMPLO, curto)
    (curto / "corpo.txt").write_text("Texto curto demais para gerar três blocos.", encoding="utf-8")
    resultados = tmp_path / "res"

    assert _rodar(exp, dados, resultados) == 1

    erro = capsys.readouterr().err
    assert "curto" in erro and "3 blocos" in erro
    assert not (resultados / "raw.jsonl").exists()  # nenhuma execução foi feita


def test_docs_filtra_e_valida_nomes(exp, dados, tmp_path, capsys):
    shutil.copytree(EXEMPLO, dados / "doc_b")
    resultados = tmp_path / "res"

    assert _rodar(exp, dados, resultados, "--runs", "1", "--docs", "doc_b") == 0
    linhas = [json.loads(l) for l in (resultados / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {l["doc_id"] for l in linhas} == {"doc_b"}

    assert _rodar(exp, dados, tmp_path / "outra", "--docs", "nao_existe") == 1
    assert "nao_existe" in capsys.readouterr().err


def test_resume_com_parametros_diferentes_aborta(exp, dados, tmp_path, capsys):
    resultados = tmp_path / "res"
    assert _rodar(exp, dados, resultados, "--runs", "1") == 0
    (resultados / "raw.jsonl").write_text(
        (resultados / "raw.jsonl").read_text(encoding="utf-8").replace('"chunk_size": 3000', '"chunk_size": 2000'),
        encoding="utf-8",
    )

    assert _rodar(exp, dados, resultados, "--runs", "1", "--resume") == 1
    assert "chunk_size" in capsys.readouterr().err


def test_lote_com_servidor_simulado_registra_tokens_e_truncamento(exp, dados, tmp_path):
    chamadas = []

    def servidor(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        chamadas.append(corpo)
        # prompt do documento inteiro (maior) estoura 95% de num_ctx=1000; blocos de 3000 caracteres não
        tokens = 990 if len(corpo["messages"][0]["content"]) > 7000 else 300
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Síntese: responsabilidade objetiva, R$ 10.000,00, recurso desprovido."},
                               "finish_reason": "stop"}],
                  "usage": {"prompt_tokens": tokens, "completion_tokens": 20}},
        )  # fmt: skip

    summarizer = RamalamaSummarizer(
        url="http://servidor.teste", model="llama3.1:8b", num_ctx=1000,
        client=httpx.Client(transport=httpx.MockTransport(servidor)),
    )  # fmt: skip
    documentos = exp.carregar_documentos(dados, None)
    for d in documentos:
        d.texto_anonimizado = d.corpo
    resultados = tmp_path / "res"
    resultados.mkdir()
    raw = resultados / "raw.jsonl"

    exp.executar_lote(documentos, summarizer, "ramalama", [42, 43], 3000, 600, raw, set(), "presidio_pt")

    linhas = exp.ler_raw(raw)
    assert len(linhas) == 6
    inteiro = [l for l in linhas if l["configuracao"] == "inteiro"]
    assert all(l["truncamento_suspeito"] for l in inteiro)
    assert not any(l["truncamento_suspeito"] for l in linhas if l["configuracao"] != "inteiro")
    com_sobreposicao = next(l for l in linhas if l["configuracao"] == "blocos_com_sobreposicao")
    assert len(com_sobreposicao["extracoes_parciais"]) == com_sobreposicao["n_blocos"]
    assert com_sobreposicao["tokens"]["prompt"] == 300 * (com_sobreposicao["n_blocos"] + 1)
    assert [c["etapa"] for c in com_sobreposicao["chamadas"]][-1] == "reduce"
    assert {c["seed"] for c in chamadas} == {42, 43}

    assert exp.tokens_do_documento(linhas, "doc_a") == 990

    exp.escrever_markdown(resultados / "summary.md", linhas, dados)
    md = (resultados / "summary.md").read_text(encoding="utf-8")
    assert "EXECUÇÃO DE TESTE" not in md
    assert "truncamento suspeito" in md
    assert "| doc_a | " in md


def test_media_e_desvio_padrao(exp):
    media, dp = exp.media_dp([0.2, 0.4, 0.6])

    assert media == pytest.approx(0.4)
    assert dp == pytest.approx(0.2)
    assert exp.media_dp([0.5]) == (0.5, 0.0)


def test_raw_registra_o_modelo_servido_e_resume_recusa_outro_arquivo(exp, dados, tmp_path):
    def servidor(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"}]})
        if request.url.path == "/props":
            return httpx.Response(200, json={"default_generation_settings": {"n_ctx": 16384}, "build_info": "b1",
                                             "model_path": "/mnt/models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "responsabilidade objetiva"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 5}})  # fmt: skip

    summarizer = RamalamaSummarizer(url="http://servidor.teste", client=httpx.Client(transport=httpx.MockTransport(servidor)))
    summarizer.verificar_disponibilidade()
    documentos = exp.carregar_documentos(dados, None)
    for d in documentos:
        d.texto_anonimizado = d.corpo
    resultados = tmp_path / "res"
    resultados.mkdir()
    raw = resultados / "raw.jsonl"

    exp.executar_lote(documentos, summarizer, "ramalama", [42], 3000, 600, raw, set(), "presidio_pt")

    linha = exp.ler_raw(raw)[0]
    assert linha["modelo"] == "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
    assert linha["modelo_arquivo"] == "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
    assert (linha["servidor_build"], linha["n_ctx_servidor"]) == ("b1", 16384)

    exp.escrever_markdown(resultados / "summary.md", exp.ler_raw(raw), dados)
    assert "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf" in (resultados / "summary.md").read_text(encoding="utf-8")

    # Reiniciar o servidor com outra quantização muda o experimento: --resume deve recusar.
    outros = {**exp.montar_parametros(summarizer, "ramalama", 3000, 600), "modelo_arquivo": "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf"}
    with pytest.raises(exp.ErroExperimento, match="modelo_arquivo"):
        exp.verificar_compatibilidade(exp.ler_raw(raw), outros)


def test_raw_registra_parametros_de_geracao_e_hash_dos_prompts(exp, dados, tmp_path):
    import hashlib

    from app.core.config import get_settings

    resultados = tmp_path / "res"
    assert _rodar(exp, dados, resultados, "--runs", "2") == 0

    linhas = exp.ler_raw(resultados / "raw.jsonl")
    prompts = RAIZ / "app" / "summarization" / "prompts"
    for l in linhas:
        assert l["temperature"] == get_settings().llm_temperature
        assert l["max_tokens"] == get_settings().llm_num_predict
        assert l["prompt_map_sha256"] == hashlib.sha256((prompts / "map.txt").read_bytes()).hexdigest()
        assert l["prompt_reduce_sha256"] == hashlib.sha256((prompts / "reduce.txt").read_bytes()).hexdigest()
    assert {l["seed"] for l in linhas} == {42, 43}  # a seed continua por linha
    md = (resultados / "summary.md").read_text(encoding="utf-8")
    assert f"max_tokens={get_settings().llm_num_predict}" in md and "Prompts (SHA-256)" in md


def test_out_grava_em_outra_pasta_sem_tocar_na_primeira_rodada(exp, dados, tmp_path):
    rodada1, rodada2 = tmp_path / "results", tmp_path / "results" / "rodada2"
    assert _rodar(exp, dados, rodada1, "--runs", "1") == 0
    antes = (rodada1 / "raw.jsonl").read_bytes()

    assert _rodar(exp, dados, rodada2, "--runs", "1") == 0

    assert (rodada1 / "raw.jsonl").read_bytes() == antes
    assert (rodada2 / "raw.jsonl").is_file() and (rodada2 / "summary.md").is_file()


def test_resume_recusa_outro_max_tokens_ou_outros_prompts(exp, dados, tmp_path, capsys):
    resultados = tmp_path / "res"
    assert _rodar(exp, dados, resultados, "--runs", "1") == 0
    raw = resultados / "raw.jsonl"
    original = raw.read_text(encoding="utf-8")

    raw.write_text(original.replace('"max_tokens": ', '"max_tokens": 7', 1), encoding="utf-8")
    assert _rodar(exp, dados, resultados, "--runs", "1", "--resume") == 1
    assert "max_tokens" in capsys.readouterr().err

    raw.write_text(original.replace('"prompt_map_sha256": "', '"prompt_map_sha256": "0', 1), encoding="utf-8")
    assert _rodar(exp, dados, resultados, "--runs", "1", "--resume") == 1
    assert "prompt_map_sha256" in capsys.readouterr().err


def test_extracoes_cortadas_na_coluna_no_csv_e_no_aviso_final(exp, dados, tmp_path, capsys):
    def servidor(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        conteudo = corpo["messages"][0]["content"]
        # só o map do documento inteiro (prompt grande) bate em max_tokens
        cortado = len(conteudo) > 7000 and "TRECHO:" in conteudo
        return httpx.Response(200, json={"choices": [{"message": {"content": "responsabilidade objetiva"},
                                                       "finish_reason": "length" if cortado else "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 5}})  # fmt: skip

    summarizer = RamalamaSummarizer(url="http://servidor.teste", client=httpx.Client(transport=httpx.MockTransport(servidor)))
    documentos = exp.carregar_documentos(dados, None)
    for d in documentos:
        d.texto_anonimizado = d.corpo
    resultados = tmp_path / "res"
    resultados.mkdir()
    raw = resultados / "raw.jsonl"

    exp.executar_lote(documentos, summarizer, "ramalama", [42, 43], 3000, 600, raw, set(), "presidio_pt")

    linhas = exp.ler_raw(raw)
    cortadas = exp.chamadas_cortadas(linhas)
    assert sorted(cortadas) == [("doc_a", "inteiro", 42, "map", 0), ("doc_a", "inteiro", 43, "map", 0)]
    assert exp.extracoes_cortadas(linhas) == 2

    exp.escrever_markdown(resultados / "summary.md", linhas, dados)
    md = (resultados / "summary.md").read_text(encoding="utf-8")
    assert md.count("Extrações cortadas (length)") == 2  # cabeçalhos das tabelas por configuração e por documento
    linha_inteiro = next(t for t in md.splitlines() if t.startswith("| doc_a | inteiro"))
    assert linha_inteiro.endswith("| 2 |")  # as 2 seeds do documento inteiro tiveram o map cortado
    assert next(t for t in md.splitlines() if t.startswith("| doc_a | blocos_sem")).endswith("| 0 |")

    exp.escrever_csv(resultados / "summary.csv", exp.agrupar(linhas))
    assert "extracoes_cortadas_length" in (resultados / "summary.csv").read_text(encoding="utf-8").splitlines()[0]

    exp.avisar_chamadas_cortadas(linhas)
    erro = capsys.readouterr().err
    assert 'finish_reason = "length"' in erro and "doc_a | inteiro | seed 42 | map, bloco 0" in erro


def test_sem_chamadas_cortadas_nao_ha_aviso(exp, capsys):
    exp.avisar_chamadas_cortadas([{"doc_id": "d", "configuracao": "inteiro", "seed": 42,
                                   "chamadas": [{"etapa": "map", "indice": 0, "finish_reason": "stop"}]}])  # fmt: skip

    assert capsys.readouterr().err == ""
