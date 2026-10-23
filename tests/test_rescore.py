"""Testes do scripts/rescore.py sobre uma rodada mock (nenhuma chamada a servidor LLM)."""

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "data" / "experimento" / "exemplo_ficticio"


@pytest.fixture(scope="module")
def rescore():
    spec = importlib.util.spec_from_file_location("rescore", RAIZ / "scripts" / "rescore.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def rodada(rescore, tmp_path):
    """Uma rodada mock (2 documentos x 3 configurações x 2 seeds = 12 execuções) e seus dados."""
    dados = tmp_path / "dados"
    for nome in ("doc_a", "doc_b"):
        shutil.copytree(EXEMPLO, dados / nome)
    saida = tmp_path / "rodada"
    codigo = rescore.exp.main(["--backend", "mock", "--runs", "2", "--data-dir", str(dados), "--out", str(saida)])
    assert codigo == 0
    return {"dados": dados, "raw": saida / "raw.jsonl", "tmp": tmp_path}


def test_fluxo_completo_gera_saidas_e_nao_modifica_o_raw(rescore, rodada):
    hash_antes = hashlib.sha256(rodada["raw"].read_bytes()).hexdigest()
    out = rodada["tmp"] / "reavaliada"

    codigo = rescore.main(["--raw", str(rodada["raw"]), "--out", str(out), "--data-dir", str(rodada["dados"])])

    assert codigo == 0
    assert hashlib.sha256(rodada["raw"].read_bytes()).hexdigest() == hash_antes
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert md.count("## ") == 3 and "Extrações cortadas (length)" in md
    assert "confere com o raw.jsonl" in md
    assert "temperature=0.1 | max_tokens=" in md and "não registrado" not in md  # gravados pela rodada mock
    linhas_csv = (out / "summary.csv").read_text(encoding="utf-8").splitlines()
    assert linhas_csv[0].startswith("tabela,doc_id,configuracao_ou_comparacao,n")
    assert sum(1 for l in linhas_csv if l.startswith("configuracao,")) == 3
    assert sum(1 for l in linhas_csv if l.startswith("documento,")) == 6
    assert sum(1 for l in linhas_csv if l.startswith("pareada,")) == 2 * (2 + 1)  # 2 documentos + a média, em 2 comparações


def test_divergencia_de_rouge_e_avisada(rescore, rodada, capsys):
    linhas_raw = rescore.exp.ler_raw(rodada["raw"])
    linhas_raw[0]["rouge"]["rouge1"]["fmeasure"] = round(linhas_raw[0]["rouge"]["rouge1"]["fmeasure"] + 0.01, 4)
    adulterado = rodada["tmp"] / "adulterado.jsonl"
    adulterado.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in linhas_raw) + "\n", encoding="utf-8")
    out = rodada["tmp"] / "out"

    assert rescore.main(["--raw", str(adulterado), "--out", str(out), "--data-dir", str(rodada["dados"])]) == 0

    assert "ROUGE divergente" in capsys.readouterr().err
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "## Avisos" in md and "rouge1.fmeasure gravado=" in md


def test_checklist_e_recalculado_com_os_arquivos_atuais(rescore, rodada):
    antes, _, mudaram_antes = rescore.reavaliar(rescore.exp.ler_raw(rodada["raw"]), rodada["dados"])
    assert mudaram_antes == 0  # mesmo checklist da rodada

    (rodada["dados"] / "doc_a" / "checklist.json").write_text(json.dumps({"valores": ["10.000,00"]}), encoding="utf-8")
    depois, _, mudaram = rescore.reavaliar(rescore.exp.ler_raw(rodada["raw"]), rodada["dados"])

    doc_a = [l for l in depois if l["doc_id"] == "doc_a"]
    assert mudaram == len(doc_a) == 6
    assert {l["checklist"]["proporcao"] for l in doc_a} == {1.0}  # a síntese mock contém "10.000,00"
    assert {l["checklist"]["proporcao"] for l in depois if l["doc_id"] == "doc_b"} == {l["checklist"]["proporcao"] for l in antes if l["doc_id"] == "doc_b"}


def test_extracoes_cortadas_entram_nas_tabelas(rescore, rodada):
    linhas = rescore.exp.ler_raw(rodada["raw"])
    linhas[0]["chamadas"] = [{"etapa": "map", "indice": 0, "finish_reason": "length"}]
    reavaliadas, _, _ = rescore.reavaliar(linhas, rodada["dados"])

    assert rescore.agregar_rescore(reavaliadas)["extracoes_cortadas"] == 1
    assert rescore.agregar_rescore([l for l in reavaliadas if l["configuracao"] != linhas[0]["configuracao"]])["extracoes_cortadas"] == 0


def test_erros_de_uso_tem_mensagem_clara(rescore, rodada, capsys):
    saida = rodada["tmp"] / "out"

    assert rescore.main(["--raw", str(rodada["tmp"] / "nao_existe.jsonl"), "--out", str(saida)]) == 1
    assert "não existe ou está vazio" in capsys.readouterr().err

    shutil.rmtree(rodada["dados"] / "doc_b")
    assert rescore.main(["--raw", str(rodada["raw"]), "--out", str(saida), "--data-dir", str(rodada["dados"])]) == 1
    assert "doc_b" in capsys.readouterr().err


def test_diferencas_pareadas(rescore):
    def l(doc, config, seed, f1):
        return {"doc_id": doc, "configuracao": config, "seed": seed, "rouge": {"rouge1": {"fmeasure": f1}}}

    linhas = []
    # doc_a: inteiro 0.5 | sem 0.2/0.4 (média 0.3) | com 0.4  -> com-sem = +0.1, inteiro-com = +0.1
    linhas += [l("doc_a", "inteiro", 42, 0.5), l("doc_a", "blocos_sem_sobreposicao", 42, 0.2),
               l("doc_a", "blocos_sem_sobreposicao", 43, 0.4), l("doc_a", "blocos_com_sobreposicao", 42, 0.4)]  # fmt: skip
    # doc_b: inteiro 0.1 | sem 0.5 | com 0.3  -> com-sem = -0.2, inteiro-com = -0.2
    linhas += [l("doc_b", "inteiro", 42, 0.1), l("doc_b", "blocos_sem_sobreposicao", 42, 0.5), l("doc_b", "blocos_com_sobreposicao", 42, 0.3)]

    r = rescore.diferencas_pareadas(linhas)

    com_sem = r["blocos_com_sobreposicao − blocos_sem_sobreposicao"]
    assert com_sem["por_documento"] == pytest.approx({"doc_a": 0.1, "doc_b": -0.2})
    assert com_sem["media"] == pytest.approx(-0.05) and com_sem["a_favor"] == 1 and com_sem["n"] == 2
    inteiro_com = r["inteiro − blocos_com_sobreposicao"]
    assert inteiro_com["por_documento"] == pytest.approx({"doc_a": 0.1, "doc_b": -0.2})
    assert inteiro_com["a_favor"] == 1
