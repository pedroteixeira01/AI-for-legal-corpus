"""Reavalia uma rodada já executada, sem chamar o modelo.

Lê o raw.jsonl da rodada (somente leitura) e recalcula:

  - o checklist factual, com os checklist.json ATUAIS de data/experimento/<doc_id>/;
  - o ROUGE, com o mesmo avaliador da API (e confere contra o valor gravado no raw.jsonl).

Saídas em --out: summary.md e summary.csv, com as médias por configuração e por documento, o
número de extrações cortadas (finish_reason = length) e as diferenças pareadas de ROUGE-1 F1
entre configurações. O raw.jsonl original não é modificado.

Uso:
    python scripts/rescore.py --raw results/rodada1_512_replicacao/raw.jsonl \\
        --out results/rodada1_reavaliada
"""

import argparse
import csv
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Tuple

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_experiment as exp  # noqa: E402  (reaproveita leitura do raw, agregação e tabelas)
from app.evaluation.service import avaliar_checklist, carregar_checklist, get_evaluator  # noqa: E402

TOLERANCIA_ROUGE = 1e-4


class ErroRescore(Exception):
    """Erro de uso: dados ausentes ou inconsistentes (a mensagem diz o que corrigir)."""


# --------------------------------------------------------------------------- reavaliação


def reavaliar(linhas_raw: List[dict], data_dir: Path) -> Tuple[List[dict], List[str], int]:
    """Recalcula ROUGE e checklist de cada execução. Devolve (linhas, avisos, nº de checklists que mudaram)."""
    evaluator = get_evaluator()
    checklists: Dict[str, dict] = {}
    ementas: Dict[str, str] = {}
    avisos: List[str] = []
    mudaram = 0
    for doc_id in sorted({l["doc_id"] for l in linhas_raw}):
        pasta = data_dir / doc_id
        try:
            checklists[doc_id] = carregar_checklist(pasta / "checklist.json")
            ementas[doc_id] = (pasta / "ementa.txt").read_text(encoding="utf-8").strip()
        except (OSError, ValueError) as exc:
            raise ErroRescore(f"{pasta}: {exc}") from exc

    saida = []
    for l in linhas_raw:
        rouge = evaluator.calcular_metricas(l["sintese"], ementas[l["doc_id"]])
        for tipo, valores in rouge.items():
            for m, novo in valores.items():
                antigo = l["rouge"][tipo][m]
                if abs(novo - antigo) > TOLERANCIA_ROUGE * 1.001:
                    avisos.append(
                        f"ROUGE divergente em {l['doc_id']} | {l['configuracao']} | seed {l['seed']}: "
                        f"{tipo}.{m} gravado={antigo} recalculado={novo}"
                    )
        checklist = avaliar_checklist(l["sintese"], checklists[l["doc_id"]])
        if abs(checklist["proporcao"] - l["checklist"]["proporcao"]) > 1e-9:
            mudaram += 1
        saida.append({**l, "rouge": rouge, "checklist": checklist})
    return saida, avisos, mudaram


# --------------------------------------------------------------------------- agregação


def agregar_rescore(linhas: List[dict]) -> dict:
    ag = {
        "n": len(linhas),
        "extracoes_cortadas": exp.extracoes_cortadas(linhas),
        "checklist": exp.media_dp([100 * l["checklist"]["proporcao"] for l in linhas]),
    }
    for metrica in exp.METRICAS:
        ag[metrica] = exp.media_dp([l["rouge"][metrica]["fmeasure"] for l in linhas])
    return ag


def diferencas_pareadas(linhas: List[dict]) -> dict:
    """Diferença de ROUGE-1 F1 por documento (média das seeds de cada configuração) entre configurações."""
    por_doc: Dict[str, Dict[str, float]] = {}
    for doc_id in sorted({l["doc_id"] for l in linhas}):
        por_doc[doc_id] = {
            c: statistics.fmean(l["rouge"]["rouge1"]["fmeasure"] for l in linhas if l["doc_id"] == doc_id and l["configuracao"] == c)
            for c in exp.CONFIGURACOES
            if any(l["doc_id"] == doc_id and l["configuracao"] == c for l in linhas)
        }
    comparacoes = {
        "blocos_com_sobreposicao − blocos_sem_sobreposicao": (exp.COM_SOBREPOSICAO, exp.SEM_SOBREPOSICAO),
        "inteiro − blocos_com_sobreposicao": (exp.INTEIRO, exp.COM_SOBREPOSICAO),
    }
    resultado = {}
    for nome, (a, b) in comparacoes.items():
        diffs = {d: v[a] - v[b] for d, v in por_doc.items() if a in v and b in v}
        resultado[nome] = {
            "por_documento": diffs,
            "media": statistics.fmean(diffs.values()) if diffs else float("nan"),
            "a_favor": sum(1 for v in diffs.values() if v > 0),
            "n": len(diffs),
        }
    return resultado


# --------------------------------------------------------------------------- saída


def escrever_csv(caminho: Path, linhas: List[dict]) -> None:
    """Formato longo: a coluna `tabela` diz se a linha é por configuração, por documento ou uma
    diferença pareada (nesta, `diff_rouge1_f1` é a diferença do documento, ou a média quando
    doc_id = TODOS, e `docs_a_favor` só aparece na linha da média)."""
    colunas = ["tabela", "doc_id", "configuracao_ou_comparacao", "n"]
    for m in exp.METRICAS:
        colunas += [f"{m}_f1_media", f"{m}_f1_dp"]
    colunas += ["checklist_pct_media", "checklist_pct_dp", "extracoes_cortadas_length", "diff_rouge1_f1", "docs_a_favor"]

    def agregado(tabela: str, doc_id: str, rotulo: str, grupo: List[dict]) -> dict:
        ag = agregar_rescore(grupo)
        linha = {"tabela": tabela, "doc_id": doc_id, "configuracao_ou_comparacao": rotulo, "n": ag["n"],
                 "checklist_pct_media": f"{ag['checklist'][0]:.2f}", "checklist_pct_dp": f"{ag['checklist'][1]:.2f}",
                 "extracoes_cortadas_length": ag["extracoes_cortadas"]}  # fmt: skip
        for m in exp.METRICAS:
            linha[f"{m}_f1_media"], linha[f"{m}_f1_dp"] = f"{ag[m][0]:.4f}", f"{ag[m][1]:.4f}"
        return linha

    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, restval="")
        w.writeheader()
        for c in exp.CONFIGURACOES:
            grupo = [l for l in linhas if l["configuracao"] == c]
            if grupo:
                w.writerow(agregado("configuracao", exp.TODOS, c, grupo))
        for d in sorted({l["doc_id"] for l in linhas}):
            for c in exp.CONFIGURACOES:
                grupo = [l for l in linhas if l["doc_id"] == d and l["configuracao"] == c]
                if grupo:
                    w.writerow(agregado("documento", d, c, grupo))
        for nome, r in diferencas_pareadas(linhas).items():
            for d, v in r["por_documento"].items():
                w.writerow({"tabela": "pareada", "doc_id": d, "configuracao_ou_comparacao": nome, "diff_rouge1_f1": f"{v:.4f}"})
            w.writerow({"tabela": "pareada", "doc_id": exp.TODOS, "configuracao_ou_comparacao": nome, "n": r["n"],
                        "diff_rouge1_f1": f"{r['media']:.4f}", "docs_a_favor": r["a_favor"]})  # fmt: skip


def escrever_markdown(caminho: Path, linhas: List[dict], args, avisos: List[str], mudaram: int) -> None:
    ref = linhas[0]
    doc_ids = sorted({l["doc_id"] for l in linhas})
    colunas = ["ROUGE-1 F1", "ROUGE-2 F1", "ROUGE-L F1", "Checklist (%)", "Extrações cortadas (length)"]

    def celulas(ag: dict) -> str:
        return " | ".join(
            [exp._fmt(ag["rouge1"]), exp._fmt(ag["rouge2"]), exp._fmt(ag["rougeL"]), exp._fmt(ag["checklist"], 1), str(ag["extracoes_cortadas"])]
        )

    def tabela(rotulos: List[str], grupos: List[List[dict]], primeira: str) -> List[str]:
        cab = f"| {primeira} | Execuções | " + " | ".join(colunas) + " |"
        sep = "|" + "---|" * (primeira.count("|") + 1) + "---:|" * (len(colunas) + 1)
        corpo = [f"| {rotulo} | {len(grupo)} | {celulas(agregar_rescore(grupo))} |" for rotulo, grupo in zip(rotulos, grupos)]
        return [cab, sep, *corpo]

    saida = [
        "# Resultados reavaliados",
        "",
        f"- Origem: `{args.raw}` ({len(linhas)} execuções; o arquivo não foi modificado)",
        f"- Modelo: `{ref.get('modelo', '—')}`" + (f" | arquivo: `{ref['modelo_arquivo']}`" if ref.get("modelo_arquivo") else ""),
        f"- Geração na rodada original: temperature={ref.get('temperature', 'não registrado')} | "
        f"max_tokens={ref.get('max_tokens', 'não registrado')} | seeds {sorted({l['seed'] for l in linhas})}",
        f"- Checklist: recalculado com os `checklist.json` atuais ({mudaram} de {len(linhas)} execuções mudaram de valor)",
        f"- ROUGE: recalculado com o avaliador atual; {'divergências acima de 0,0001 listadas em Avisos' if avisos else 'confere com o raw.jsonl (nenhuma divergência acima de 0,0001)'}",
        "",
        "## 1. Resultados por configuração (todos os documentos)",
        "",
        *tabela(
            list(exp.CONFIGURACOES),
            [[l for l in linhas if l["configuracao"] == c] for c in exp.CONFIGURACOES],
            "Configuração",
        ),
        "",
        "O desvio padrão desta tabela mistura a variação entre documentos e entre seeds. "
        "*Extrações cortadas*: chamadas *map* com `finish_reason = length`.",
        "",
        "## 2. Resultados por documento",
        "",
    ]
    rotulos, grupos = [], []
    for d in doc_ids:
        for c in exp.CONFIGURACOES:
            g = [l for l in linhas if l["doc_id"] == d and l["configuracao"] == c]
            if g:
                rotulos.append(f"{d} | {c}")
                grupos.append(g)
    saida += tabela(rotulos, grupos, "Documento | Configuração")

    pareadas = diferencas_pareadas(linhas)
    nomes = list(pareadas)
    saida += [
        "",
        "## 3. Diferenças pareadas de ROUGE-1 F1 (por documento, média das seeds)",
        "",
        "| Documento | " + " | ".join(nomes) + " |",
        "|---|" + "---:|" * len(nomes),
    ]
    for d in doc_ids:
        saida.append(f"| {d} | " + " | ".join(f"{pareadas[n]['por_documento'][d]:+.4f}" if d in pareadas[n]["por_documento"] else "—" for n in nomes) + " |")
    saida.append("| **Média** | " + " | ".join(f"**{pareadas[n]['media']:+.4f}**" for n in nomes) + " |")
    saida.append("| **Documentos a favor** | " + " | ".join(f"**{pareadas[n]['a_favor']} de {pareadas[n]['n']}**" for n in nomes) + " |")
    saida += ["", "A favor = a primeira configuração da comparação teve ROUGE-1 F1 maior (diferença > 0)."]

    if avisos:
        saida += ["", "## Avisos", "", *[f"- {a}" for a in avisos]]
    caminho.write_text("\n".join(saida) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- main


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", type=Path, required=True, help="raw.jsonl da rodada (somente leitura)")
    p.add_argument("--out", type=Path, required=True, help="pasta de saída (summary.md e summary.csv)")
    p.add_argument("--data-dir", type=Path, default=RAIZ / "data" / "experimento", help="pasta com os checklist.json e ementa.txt")
    args = p.parse_args(argv)

    try:
        linhas_raw = exp.ler_raw(args.raw)
        if not linhas_raw:
            raise ErroRescore(f"{args.raw} não existe ou está vazio.")
        linhas, avisos, mudaram = reavaliar(linhas_raw, args.data_dir)
    except (ErroRescore, exp.ErroExperimento) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    escrever_markdown(args.out / "summary.md", linhas, args, avisos, mudaram)
    escrever_csv(args.out / "summary.csv", linhas)
    for a in avisos:
        print(f"AVISO: {a}", file=sys.stderr)
    print(f"{len(linhas)} execuções reavaliadas ({mudaram} com checklist alterado) -> {args.out}/summary.md e summary.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
