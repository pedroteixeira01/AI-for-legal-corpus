"""Extrai precedentes da Revista de Súmulas do STJ (vol. 43) para o experimento.

Uso: python scripts/extrair_revista_sumulas.py <revista_v43.pdf> data/experimento

Para cada súmula selecionada:
  - corrige ligaduras tipográficas (fi, fl, ff, Th) que o PDF codifica como
    caracteres de uso privado seguidos de um espaço espúrio;
  - remove cabeçalhos e números de página da revista;
  - desfaz as quebras de linha da diagramação (mantendo hífens legítimos);
  - separa cabeçalho, ementa, parágrafo do acórdão e corpo (relatório + votos).
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

URL_REVISTA = "https://www.stj.jus.br/docs_internet/revista/eletronica/stj-revista-sumulas-2017_43.pdf"

# índice da página (0-based) do início e do fim (exclusivo) de cada seção
SECOES = {
    473: (66, 86),
    474: (86, 96),
    475: (96, 114),
    478: (162, 176),
    479: (176, 196),
    498: (452, 472),
}

LIGADURAS = {
    "\ue00b": "fi", "\ue000": "fi", "\ufb01": "fi",
    "\ue001": "fl", "\ue00c": "fl", "\ufb02": "fl",
    "\ue00d": "Th",
    "\ue00e": "ff", "\ue002": "ff",
    "\ue00f": "(", "\ue010": "-", "\ue011": ")",
}
RE_LIG = re.compile("([" + "".join(LIGADURAS) + "]) ?")

CABECALHOS = (
    re.compile(r"^SUPERIOR TRIBUNAL DE JUSTIÇA$"),
    re.compile(r"^SÚMULAS - PRECEDENTES$"),
    re.compile(r"^RSSTJ, a\. 9, \(43\):.*$"),
    re.compile(r"^\d{1,3}$"),
)
RE_CASO = re.compile(r"^(RECURSO ESPECIAL|EMBARGOS|AGRAVO|CONFLITO|HABEAS)[^\n]* N\. [\d.]+-[A-Z]{2}")
FIM_PARAGRAFO = tuple(".:;!?)\"”’")
MESES = {m: i for i, m in enumerate(
    ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
     "agosto", "setembro", "outubro", "novembro", "dezembro"], 1)}


def corrigir_ligaduras(t: str) -> str:
    return RE_LIG.sub(lambda m: LIGADURAS[m.group(1)], t)


# Espaçamento de letras herdado da diagramação, conferido manualmente no PDF.
CORRECOES_PONTUAIS = {"P ERMANENT E": "PERMANENTE"}


def corrigir_pontuais(t: str) -> str:
    for errado, certo in CORRECOES_PONTUAIS.items():
        t = t.replace(errado, certo)
    return t


def desquebrar(bloco: str) -> str:
    """Junta as linhas de um parágrafo; hífen no fim da linha é mantido (todos
    os casos no volume são hífens legítimos, como 'conta-corrente' ou '-se')."""
    linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
    out = ""
    for l in linhas:
        if not out:
            out = l
        elif out.endswith("-"):
            out += l
        else:
            out += " " + l
    return re.sub(r"\s{2,}", " ", out).strip()


def paragrafos(doc, ini: int, fim: int) -> list[str]:
    pars: list[str] = []
    for k in range(ini, fim):
        blocos = [b[4] for b in doc[k].get_text("blocks") if b[6] == 0]
        pagina = []
        for b in blocos:
            p = corrigir_pontuais(desquebrar(corrigir_ligaduras(b)))
            if not p or any(rx.match(p) for rx in CABECALHOS):
                continue
            pagina.append(p)
        if not pagina:
            continue
        # parágrafo que atravessa a quebra de página
        if pars and not pars[-1].endswith(FIM_PARAGRAFO) and (pagina[0][0].islower() or pars[-1].endswith("-")):
            sep = "" if pars[-1].endswith("-") else " "
            pars[-1] = pars[-1] + sep + pagina.pop(0)
        pars.extend(pagina)
    return pars


def indice(pars, rotulo, desde=0):
    for i in range(desde, len(pars)):
        if pars[i].strip() == rotulo:
            return i
    raise ValueError(f"rótulo {rotulo!r} não encontrado")


def extrair(doc, sumula: int, ini: int, fim: int) -> dict:
    enunciado_pars = paragrafos(doc, ini, ini + 1)
    enunciado = enunciado_pars[1] if len(enunciado_pars) > 1 else ""

    inicio_caso = next(k for k in range(ini + 1, fim) if RE_CASO.match(doc[k].get_text().strip()))
    pars = paragrafos(doc, inicio_caso, fim)

    i_ementa = indice(pars, "EMENTA")
    i_acordao = indice(pars, "ACÓRDÃO", i_ementa)
    i_relatorio = indice(pars, "RELATÓRIO", i_acordao)

    while pars and re.fullmatch(r"Súmula n\. \d+", pars[-1]):
        pars.pop()  # página divisória da súmula seguinte
    cabecalho = pars[:i_ementa]
    ementa = "\n".join(pars[i_ementa + 1:i_acordao])
    acordao = "\n".join(pars[i_acordao + 1:i_relatorio])
    corpo = "\n".join(pars[i_relatorio:])

    caso = cabecalho[0]
    m_num = re.match(r"(.+?) N\. ([\d.]+-[A-Z]{2})", caso)
    relator = next((re.sub(r"^Relator(a)?:\s*", "", c) for c in cabecalho
                    if c.startswith("Relator")), "")
    relator = relator.split(" Recorrente")[0].split(" Embargante")[0].split(" Suscitante")[0].strip()

    m_data = re.search(r"\(DF\), (\d{1,2}) de (\w+) de (\d{4}) \(data do julgamento\)", acordao)
    data_julg = f"{m_data.group(3)}-{MESES[m_data.group(2).lower()]:02d}-{int(m_data.group(1)):02d}" if m_data else None
    m_dje = re.search(r"DJe (\d{1,2})º?\.(\d{1,2})\.(\d{4})", acordao)
    dje = f"{m_dje.group(3)}-{int(m_dje.group(2)):02d}-{int(m_dje.group(1)):02d}" if m_dje else None
    m_org = re.search(r"Ministros da (.+?) do Superior Tribunal de Justiça", acordao)

    sigla = {"Recurso Especial": "resp"}.get(m_num.group(1).title(), re.sub(r"[^a-z]+", "", m_num.group(1).lower()))
    doc_id = f"stj_{sigla}_" + m_num.group(2).replace(".", "").replace("-", "_").lower()
    return {
        "doc_id": doc_id,
        "ementa": ementa,
        "acordao": acordao,
        "corpo": corpo,
        "metadados": {
            "tribunal": "STJ",
            "classe": m_num.group(1).title(),
            "numero": m_num.group(2),
            "orgao_julgador": m_org.group(1) if m_org else None,
            "relator": relator,
            "data_julgamento": data_julg,
            "dje": dje,
            "sumula": sumula,
            "enunciado_sumula": enunciado,
            "fonte": "Revista de Súmulas do Superior Tribunal de Justiça, v. 43, nov. 2017",
            "paginas_pdf": f"{inicio_caso + 1}-{fim}",
            "link": URL_REVISTA,
            "data_acesso": "PREENCHER",
            "observacao": ("Partes e advogados omitidos dos metadados (minimização de dados). "
                           "Ementa e parágrafo do acórdão excluídos do corpo para evitar que a "
                           "referência ou a tese apareçam literalmente na entrada do modelo."),
        },
    }


def main():
    if len(sys.argv) != 3:
        sys.exit("uso: python extrair_revista_sumulas.py <revista_v43.pdf> <pasta_saida>")
    doc = pymupdf.open(sys.argv[1])
    SAIDA = Path(sys.argv[2])
    SAIDA.mkdir(parents=True, exist_ok=True)
    resumo = []
    for sumula, (ini, fim) in SECOES.items():
        r = extrair(doc, sumula, ini, fim)
        pasta = SAIDA / r["doc_id"]
        pasta.mkdir(exist_ok=True)
        (pasta / "corpo.txt").write_text(r["corpo"] + "\n", encoding="utf-8")
        (pasta / "ementa.txt").write_text(r["ementa"] + "\n", encoding="utf-8")
        (pasta / "acordao.txt").write_text(r["acordao"] + "\n", encoding="utf-8")
        (pasta / "metadados.json").write_text(
            json.dumps(r["metadados"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        resumo.append((r["doc_id"], sumula, len(r["corpo"]), len(r["ementa"]), r["metadados"]))
    for doc_id, s, nc, ne, md in resumo:
        print(f"{doc_id:42} Súmula {s} | corpo {nc:>6} | ementa {ne:>5} | "
              f"{md['orgao_julgador']} | {md['relator']} | julg {md['data_julgamento']} | DJe {md['dje']}")


if __name__ == "__main__":
    main()
