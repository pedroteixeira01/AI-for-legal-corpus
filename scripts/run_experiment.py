"""Experimento de síntese: três configurações de blocos x N repetições por documento.

Para cada pasta `data/experimento/<doc_id>/` (com corpo.txt, ementa.txt, checklist.json e
metadados.json), o corpo é anonimizado com o mesmo serviço da API e sintetizado por
map-reduce em três configurações:

    inteiro                  o documento todo como um único bloco
    blocos_sem_sobreposicao  CHUNK_SIZE caracteres, sobreposição 0
    blocos_com_sobreposicao  CHUNK_SIZE caracteres, sobreposição CHUNK_OVERLAP

Cada síntese é comparada com a ementa (ROUGE) e com o checklist factual. Saídas em
`--out` (padrão `results/`): raw.jsonl (uma linha por execução), summary.csv e summary.md.
Cada linha do raw.jsonl registra o modelo servido, temperature, max_tokens, seed e o
SHA-256 dos prompts. Uma segunda rodada, sem sobrescrever a primeira:
    python scripts/run_experiment.py --out results/rodada2

Uso:
    python scripts/run_experiment.py                      # lote real (exige `ramalama serve`)
    python scripts/run_experiment.py --backend mock --runs 1   # teste do fluxo, sem servidor LLM
    python scripts/run_experiment.py --resume             # continua um lote interrompido
"""

import argparse
import csv
import dataclasses
import json
import logging
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Permite rodar via `python scripts/run_experiment.py` a partir da raiz do projeto.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.anonymization.service import get_anonymizer  # noqa: E402
from app.chunking.schemas import LegalDocumentChunk  # noqa: E402
from app.chunking.service import LegalChunker  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.evaluation.service import avaliar_checklist, carregar_checklist, get_evaluator  # noqa: E402
from app.summarization.service import (  # noqa: E402
    BaseSummarizer,
    RamalamaSummarizer,
    SummarizerError,
    criar_summarizer,
)

logger = logging.getLogger("experimento")

INTEIRO = "inteiro"
SEM_SOBREPOSICAO = "blocos_sem_sobreposicao"
COM_SOBREPOSICAO = "blocos_com_sobreposicao"
CONFIGURACOES = (INTEIRO, SEM_SOBREPOSICAO, COM_SOBREPOSICAO)
MIN_BLOCOS = 3
METRICAS = ("rouge1", "rouge2", "rougeL")
TODOS = "TODOS"


class ErroExperimento(Exception):
    """Erro de uso (dados ausentes, validação prévia, resultados incompatíveis)."""


@dataclasses.dataclass
class Documento:
    doc_id: str
    corpo: str
    ementa: str
    checklist: Dict[str, List[str]]
    metadados: dict
    texto_anonimizado: str = ""


# --------------------------------------------------------------------------- entrada


def carregar_documentos(data_dir: Path, selecionados: List[str] | None) -> List[Documento]:
    if not data_dir.is_dir():
        raise ErroExperimento(f"Pasta de dados não encontrada: {data_dir}")
    pastas = sorted(p for p in data_dir.iterdir() if p.is_dir())
    disponiveis = [p.name for p in pastas]
    if selecionados:
        desconhecidos = [d for d in selecionados if d not in disponiveis]
        if desconhecidos:
            raise ErroExperimento(f"Documento(s) inexistente(s): {desconhecidos}. Disponíveis: {disponiveis}")
        pastas = [p for p in pastas if p.name in selecionados]
    if not pastas:
        raise ErroExperimento(f"Nenhum documento em {data_dir} (cada documento é uma subpasta; veja o README da pasta).")

    documentos = []
    for pasta in pastas:
        faltando = [n for n in ("corpo.txt", "ementa.txt", "checklist.json", "metadados.json") if not (pasta / n).is_file()]
        if faltando:
            raise ErroExperimento(f"{pasta}: arquivo(s) ausente(s): {faltando}")
        try:
            checklist = carregar_checklist(pasta / "checklist.json")
            metadados = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ErroExperimento(f"{pasta}: {exc}") from exc
        documentos.append(
            Documento(
                doc_id=pasta.name,
                corpo=(pasta / "corpo.txt").read_text(encoding="utf-8"),
                ementa=(pasta / "ementa.txt").read_text(encoding="utf-8").strip(),
                checklist=checklist,
                metadados=metadados,
            )
        )
    return documentos


# --------------------------------------------------------------------------- blocos


def montar_blocos(configuracao: str, texto: str, chunk_size: int, overlap: int) -> List[LegalDocumentChunk]:
    if configuracao == INTEIRO:
        return [LegalDocumentChunk(chunk_id=0, texto=texto, inicio_char=0, fim_char=len(texto), tamanho=len(texto))]
    sobreposicao = overlap if configuracao == COM_SOBREPOSICAO else 0
    return LegalChunker(chunk_size, sobreposicao).chunk_text(texto)


def validar_numero_de_blocos(documentos: List[Documento], chunk_size: int, overlap: int) -> None:
    """Com menos de MIN_BLOCOS blocos a comparação entre as configurações perde o sentido."""
    curtos = []
    for doc in documentos:
        for config in (SEM_SOBREPOSICAO, COM_SOBREPOSICAO):
            n = len(montar_blocos(config, doc.texto_anonimizado, chunk_size, overlap))
            if n < MIN_BLOCOS:
                curtos.append(f"  - {doc.doc_id}: {n} bloco(s) em '{config}' ({len(doc.texto_anonimizado)} caracteres)")
    if curtos:
        raise ErroExperimento(
            f"Cada documento precisa gerar pelo menos {MIN_BLOCOS} blocos com CHUNK_SIZE={chunk_size}; "
            "caso contrário, 'inteiro' e 'blocos' não são comparáveis. Documentos curtos demais:\n"
            + "\n".join(curtos)
            + "\nUse documentos maiores ou remova-os do lote (--docs)."
        )


# --------------------------------------------------------------------------- execução


def _chave(linha: dict) -> tuple:
    return (linha["doc_id"], linha["configuracao"], linha["seed"])


def ler_raw(caminho: Path) -> List[dict]:
    if not caminho.is_file():
        return []
    linhas = []
    with caminho.open(encoding="utf-8") as f:
        for numero, texto in enumerate(f, start=1):
            if texto.strip():
                try:
                    linhas.append(json.loads(texto))
                except json.JSONDecodeError as exc:
                    raise ErroExperimento(f"{caminho}, linha {numero}: JSON inválido ({exc}).") from exc
    return linhas


def verificar_compatibilidade(existentes: List[dict], parametros: dict) -> None:
    """Retomar um lote com modelo ou chunking diferentes misturaria condições no mesmo resultado."""
    for linha in existentes:
        for campo, valor in parametros.items():
            if linha.get(campo) != valor:
                raise ErroExperimento(
                    f"raw.jsonl foi gerado com {campo}={linha.get(campo)!r}, mas esta execução usa {valor!r}. "
                    "Use outra pasta (--out) ou apague o raw.jsonl."
                )


def montar_parametros(summarizer: BaseSummarizer, backend: str, chunk_size: int, overlap: int) -> dict:
    """Condições do experimento gravadas em cada linha do raw.jsonl e conferidas no --resume."""
    return {
        **summarizer.parametros_do_modelo(),
        **summarizer.parametros_de_geracao(),  # temperature, max_tokens e SHA-256 dos prompts (a seed é por linha)
        "backend": backend,
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
    }


def executar_lote(
    documentos: List[Documento],
    summarizer: BaseSummarizer,
    backend: str,
    seeds: List[int],
    chunk_size: int,
    overlap: int,
    raw_path: Path,
    ja_feitas: set,
    anonimizacao_modo: str,
) -> None:
    evaluator = get_evaluator()
    parametros = montar_parametros(summarizer, backend, chunk_size, overlap)
    total = len(documentos) * len(CONFIGURACOES) * len(seeds)
    feitas = 0

    with raw_path.open("a", encoding="utf-8") as saida:
        for doc in documentos:
            for config in CONFIGURACOES:
                blocos = montar_blocos(config, doc.texto_anonimizado, chunk_size, overlap)
                for execucao, seed in enumerate(seeds):
                    feitas += 1
                    rotulo = f"[{feitas}/{total}] {doc.doc_id} | {config} | seed {seed}"
                    if (doc.doc_id, config, seed) in ja_feitas:
                        print(f"{rotulo} -> já existe, pulando")
                        continue

                    resultado = summarizer.sintetizar_com_metadados(blocos, seed=seed)
                    rouge = evaluator.calcular_metricas(resultado.texto, doc.ementa)
                    checklist = avaliar_checklist(resultado.texto, doc.checklist)

                    linha = {
                        "doc_id": doc.doc_id,
                        "configuracao": config,
                        "seed": seed,
                        "execucao": execucao,
                        **parametros,
                        "anonimizacao_modo": anonimizacao_modo,
                        "n_caracteres": len(doc.texto_anonimizado),
                        "n_blocos": len(blocos),
                        "sintese": resultado.texto,
                        "extracoes_parciais": resultado.extracoes_parciais,
                        "rouge": rouge,
                        "checklist": checklist,
                        "tokens": {"prompt": resultado.tokens_prompt, "gerados": resultado.tokens_gerados},
                        "chamadas": [dataclasses.asdict(c) for c in resultado.chamadas],
                        "tempo_s": round(resultado.tempo_s, 2),
                        "truncamento_suspeito": resultado.truncamento_suspeito,
                        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                    saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
                    saida.flush()  # o lote pode levar horas: nada fica só em memória

                    aviso = "  !! TRUNCAMENTO SUSPEITO" if resultado.truncamento_suspeito else ""
                    print(
                        f"{rotulo} -> blocos={len(blocos)} ROUGE-1 F1={rouge['rouge1']['fmeasure']:.3f} "
                        f"ROUGE-L F1={rouge['rougeL']['fmeasure']:.3f} checklist={checklist['proporcao']:.0%} "
                        f"{resultado.tempo_s:.1f}s{aviso}"
                    )


# --------------------------------------------------------------------------- resumo


def media_dp(valores: List[float]) -> tuple[float, float]:
    if not valores:
        return float("nan"), float("nan")
    return statistics.fmean(valores), (statistics.stdev(valores) if len(valores) > 1 else 0.0)


def chamadas_cortadas(linhas: List[dict]) -> List[tuple]:
    """Chamadas ao LLM que terminaram com finish_reason == "length" (saída cortada em max_tokens):
    (doc_id, configuracao, seed, etapa, indice do bloco)."""
    return [
        (l["doc_id"], l["configuracao"], l["seed"], c["etapa"], c["indice"])
        for l in linhas
        for c in l["chamadas"]
        if c.get("finish_reason") == "length"
    ]


def extracoes_cortadas(linhas: List[dict]) -> int:
    """Quantas extrações do map foram cortadas (finish_reason == "length")."""
    return sum(1 for l in linhas for c in l["chamadas"] if c["etapa"] == "map" and c.get("finish_reason") == "length")


def agregar(linhas: List[dict]) -> dict:
    agregado = {
        "n": len(linhas),
        "truncamentos": sum(1 for l in linhas if l["truncamento_suspeito"]),
        "extracoes_cortadas": extracoes_cortadas(linhas),
    }
    for metrica in METRICAS:
        agregado[metrica] = media_dp([l["rouge"][metrica]["fmeasure"] for l in linhas])
    agregado["checklist"] = media_dp([100 * l["checklist"]["proporcao"] for l in linhas])
    return agregado


def _fmt(par: tuple[float, float], casas: int = 3) -> str:
    return f"{par[0]:.{casas}f} ± {par[1]:.{casas}f}"


def agrupar(linhas: List[dict]) -> Dict[tuple, List[dict]]:
    grupos: Dict[tuple, List[dict]] = {}
    for linha in linhas:
        grupos.setdefault((linha["doc_id"], linha["configuracao"]), []).append(linha)
        grupos.setdefault((TODOS, linha["configuracao"]), []).append(linha)
    return grupos


def tokens_do_documento(linhas: List[dict], doc_id: str) -> int | None:
    """Tokens do documento inteiro segundo o servidor: prompt do map na primeira execução
    ('inteiro', primeira seed)."""
    candidatas = [l for l in linhas if l["doc_id"] == doc_id and l["configuracao"] == INTEIRO]
    if not candidatas:
        return None
    primeira = min(candidatas, key=lambda l: l["execucao"])
    for chamada in primeira["chamadas"]:
        if chamada["etapa"] == "map":
            return chamada["prompt_tokens"]
    return None


def escrever_csv(caminho: Path, grupos: Dict[tuple, List[dict]]) -> None:
    colunas = ["doc_id", "configuracao", "n_execucoes", "n_blocos"]
    for metrica in METRICAS:
        colunas += [f"{metrica}_f1_media", f"{metrica}_f1_dp"]
    colunas += ["checklist_pct_media", "checklist_pct_dp", "truncamentos_suspeitos", "extracoes_cortadas_length"]
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(colunas)
        for (doc_id, config), linhas in sorted(grupos.items(), key=lambda kv: (kv[0][0] == TODOS, kv[0][0], CONFIGURACOES.index(kv[0][1]))):
            ag = agregar(linhas)
            n_blocos = linhas[0]["n_blocos"] if doc_id != TODOS else ""
            linha = [doc_id, config, ag["n"], n_blocos]
            for metrica in METRICAS:
                linha += [f"{ag[metrica][0]:.4f}", f"{ag[metrica][1]:.4f}"]
            linha += [f"{ag['checklist'][0]:.2f}", f"{ag['checklist'][1]:.2f}", ag["truncamentos"], ag["extracoes_cortadas"]]
            escritor.writerow(linha)


def escrever_markdown(caminho: Path, linhas: List[dict], data_dir: Path) -> None:
    grupos = agrupar(linhas)
    doc_ids = sorted({l["doc_id"] for l in linhas})
    ref = linhas[0]
    runs = max(len({l["seed"] for l in linhas if l["doc_id"] == d and l["configuracao"] == c}) for d in doc_ids for c in CONFIGURACOES)

    def metadado(doc_id: str, campo: str) -> str:
        arquivo = data_dir / doc_id / "metadados.json"
        try:
            return str(json.loads(arquivo.read_text(encoding="utf-8")).get(campo, "—"))
        except (OSError, ValueError):
            return "—"

    saida = ["# Resultados do experimento de síntese", ""]
    if ref["backend"] == "mock":
        saida += [
            "> **EXECUÇÃO DE TESTE (backend `mock`).** A síntese é um texto fixo que não lê o documento: "
            "estes números só validam o fluxo e **não** representam nenhum modelo.",
            "",
        ]
    saida += [
        f"- Backend: `{ref['backend']}` | modelo: `{ref['modelo']}`" + (
            f" | arquivo: `{ref['modelo_arquivo']}` | servidor: `{ref.get('servidor_build', '—')}`" if ref.get("modelo_arquivo") else ""
        ),
        f"- Chunking: CHUNK_SIZE={ref['chunk_size']} caracteres; sobreposição de `{COM_SOBREPOSICAO}` = {ref['chunk_overlap']}",
        f"- Geração: temperature={ref.get('temperature', '—')} | max_tokens={ref.get('max_tokens', '—')} | seeds "
        f"{sorted({l['seed'] for l in linhas})}",
        f"- Prompts (SHA-256): map `{str(ref.get('prompt_map_sha256', '—'))[:12]}` | reduce `{str(ref.get('prompt_reduce_sha256', '—'))[:12]}`",
        f"- Execuções por configuração: até {runs} (seeds {sorted({l['seed'] for l in linhas})}); média ± desvio padrão amostral",
        f"- Anonimização: `{ref['anonimizacao_modo']}`",
        "",
        "## 1. Corpus",
        "",
        "| Documento | Tribunal | Caracteres | Tokens (servidor) | Blocos: inteiro | Blocos: sem sobreposição | Blocos: com sobreposição |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for d in doc_ids:
        por_config = {c: next(l for l in linhas if l["doc_id"] == d and l["configuracao"] == c)["n_blocos"] for c in CONFIGURACOES if (d, c) in grupos}
        tokens = tokens_do_documento(linhas, d)
        saida.append(
            f"| {d} | {metadado(d, 'tribunal')} | {next(l for l in linhas if l['doc_id'] == d)['n_caracteres']} "
            f"| {tokens if tokens is not None else '—'} "
            + "".join(f"| {por_config.get(c, '—')} " for c in CONFIGURACOES)
            + "|"
        )
    saida += [
        "",
        "Caracteres: texto após anonimização (o que o modelo recebe). Tokens: `prompt_tokens` reportado pelo servidor "
        "para o prompt *map* do documento inteiro na primeira execução (inclui as instruções do prompt e o template de chat).",
        "",
    ]

    cabecalho = "| Configuração | Execuções | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | Checklist atendido (%) | Truncamentos suspeitos | Extrações cortadas (length) |"
    separador = "|---|---:|---:|---:|---:|---:|---:|---:|"

    def linha_tabela(rotulo: str, ag: dict) -> str:
        return (
            f"| {rotulo} | {ag['n']} | {_fmt(ag['rouge1'])} | {_fmt(ag['rouge2'])} | {_fmt(ag['rougeL'])} "
            f"| {_fmt(ag['checklist'], 1)} | {ag['truncamentos']} | {ag['extracoes_cortadas']} |"
        )

    saida += ["## 2. Resultados por configuração (todos os documentos)", "", cabecalho, separador]
    for c in CONFIGURACOES:
        if (TODOS, c) in grupos:
            saida.append(linha_tabela(c, agregar(grupos[(TODOS, c)])))
    saida += [
        "",
        "O desvio padrão desta tabela mistura a variação entre documentos e entre seeds; "
        "a tabela 3 separa por documento. *Extrações cortadas*: chamadas *map* com `finish_reason = length`, "
        "isto é, que bateram em `max_tokens` e podem ter perdido informação.",
        "",
        "## 3. Resultados por documento",
        "",
        cabecalho.replace("| Configuração", "| Documento | Configuração"),
        separador.replace("|---|", "|---|---|", 1),
    ]
    for d in doc_ids:
        for c in CONFIGURACOES:
            if (d, c) in grupos:
                saida.append(linha_tabela(f"{d} | {c}", agregar(grupos[(d, c)])))

    truncados = [l for l in linhas if l["truncamento_suspeito"]]
    if truncados:
        saida += ["", "## Avisos", ""]
        saida.append(
            f"**{len(truncados)} execução(ões) com truncamento suspeito** (`prompt_tokens` ≥ 95% de `LLM_NUM_CTX`): "
            "a entrada está no limite do contexto do servidor. Aumente `--ctx-size` (e `LLM_NUM_CTX`) ou reduza `CHUNK_SIZE`."
        )
        for l in truncados:
            saida.append(f"- {l['doc_id']} | {l['configuracao']} | seed {l['seed']}")
    caminho.write_text("\n".join(saida) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- main


def analisar_argumentos(argv: List[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=RAIZ / "data" / "experimento", help="pasta com um subdiretório por documento")
    p.add_argument("--out", "--results-dir", dest="results_dir", type=Path, default=None,
                   help="pasta de saída (raw.jsonl, summary.csv, summary.md). Padrão: results/ (ou results/mock/ com --backend mock)")  # fmt: skip
    p.add_argument("--docs", nargs="+", metavar="DOC_ID", help="roda só estes documentos")
    p.add_argument("--runs", type=int, default=3, help="repetições por configuração (seeds LLM_SEED, LLM_SEED+1, ...)")
    p.add_argument("--backend", choices=["mock", "ramalama"], default="ramalama", help="'mock' valida o fluxo sem servidor LLM")
    p.add_argument("--resume", action="store_true", help="pula execuções já presentes em raw.jsonl")
    args = p.parse_args(argv)
    if args.runs < 1:
        p.error("--runs deve ser >= 1")
    if args.results_dir is None:
        args.results_dir = RAIZ / "results" / ("mock" if args.backend == "mock" else "")
    return args


def avisar_chamadas_cortadas(linhas: List[dict]) -> None:
    """Ao final do lote, lista as chamadas cuja saída bateu em max_tokens (finish_reason == "length")."""
    cortadas = chamadas_cortadas(linhas)
    if not cortadas:
        return
    print(
        f"\nAVISO: {len(cortadas)} chamada(s) terminaram com finish_reason = \"length\" (saída cortada em max_tokens; "
        f"a informação extraída pode estar incompleta):",
        file=sys.stderr,
    )
    for doc_id, config, seed, etapa, indice in cortadas:
        print(f"  - {doc_id} | {config} | seed {seed} | {etapa}, bloco {indice}", file=sys.stderr)


def main(argv: List[str] | None = None) -> int:
    args = analisar_argumentos(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    chunk_size, overlap = settings.chunk_size, settings.chunk_overlap
    seeds = [settings.llm_seed + i for i in range(args.runs)]
    raw_path = args.results_dir / "raw.jsonl"

    try:
        documentos = carregar_documentos(args.data_dir, args.docs)

        anonymizer = get_anonymizer()
        if not anonymizer.ner_ativo:
            logger.warning(
                "Anonimização em modo degradado (somente regex): nomes NÃO são mascarados. "
                "Rode: python -m spacy download %s",
                settings.spacy_model,
            )
        for doc in documentos:
            doc.texto_anonimizado = anonymizer.sanitizar(doc.corpo)

        validar_numero_de_blocos(documentos, chunk_size, overlap)

        summarizer = criar_summarizer(args.backend)
        if isinstance(summarizer, RamalamaSummarizer):
            info = summarizer.verificar_disponibilidade()
            print(
                f"Servidor: modelo={info['modelo']} | arquivo={info['modelo_arquivo']} | "
                f"build={info['servidor_build']} | n_ctx={info['n_ctx_servidor']}"
            )

        existentes = ler_raw(raw_path)
        if existentes and not args.resume:
            raise ErroExperimento(f"{raw_path} já existe. Use --resume para continuar, ou outra pasta em --out.")
        parametros = montar_parametros(summarizer, args.backend, chunk_size, overlap)
        verificar_compatibilidade(existentes, parametros)

        args.results_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"Backend {args.backend} ({parametros['modelo']}) | {len(documentos)} documento(s) x "
            f"{len(CONFIGURACOES)} configurações x {args.runs} execução(ões) | seeds {seeds} | "
            f"temperature={parametros['temperature']} max_tokens={parametros['max_tokens']} | resultados em {args.results_dir}"
        )
        executar_lote(
            documentos, summarizer, args.backend, seeds, chunk_size, overlap, raw_path,
            ja_feitas={_chave(l) for l in existentes}, anonimizacao_modo=anonymizer.modo,
        )  # fmt: skip
    except (ErroExperimento, SummarizerError) as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        if isinstance(exc, SummarizerError) and raw_path.is_file() and raw_path.stat().st_size:
            print(f"As execuções concluídas estão em {raw_path}; retome com --resume.", file=sys.stderr)
        return 1

    linhas = ler_raw(raw_path)
    grupos = agrupar(linhas)
    escrever_csv(args.results_dir / "summary.csv", grupos)
    escrever_markdown(args.results_dir / "summary.md", linhas, args.data_dir)
    print(f"\nResumo escrito em {args.results_dir}/summary.csv e summary.md")
    avisar_chamadas_cortadas(linhas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
