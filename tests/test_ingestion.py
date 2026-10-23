import pytest

from app.ingestion.service import normalizar_ligaduras

# Caracteres de uso privado que alguns PDFs usam para as ligaduras (via chr() para ficarem visíveis).
FI_E00B, FI_E000, FI_FB01 = chr(0xE00B), chr(0xE000), chr(0xFB01)
FL_E00C, FL_E001, FL_FB02 = chr(0xE00C), chr(0xE001), chr(0xFB02)
TH_E00D = chr(0xE00D)
FF_E002, FF_E00E = chr(0xE002), chr(0xE00E)


def test_ligadura_fi_consome_o_espaco_espurio():
    assert normalizar_ligaduras(f"instituições {FI_E00B} nanceiras") == "instituições financeiras"


def test_ligadura_fl_em_abreviacao():
    assert normalizar_ligaduras(f"({FL_E00C} s. 12)") == "(fls. 12)"


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        (f"{FI_E000} nal", "final"),
        (f"{FI_E00B} nal", "final"),
        (f"{FI_FB01} nal", "final"),
        (f"{FL_E001} uxo", "fluxo"),
        (f"{FL_E00C} uxo", "fluxo"),
        (f"{FL_FB02} uxo", "fluxo"),
        (f"{TH_E00D} omas", "Thomas"),
        (f"su{FF_E002} ixo", "suffixo"),
        (f"e{FF_E00E} ect", "effect"),
    ],
)
def test_cada_ligadura_mapeada(entrada, esperado):
    assert normalizar_ligaduras(entrada) == esperado


def test_sem_espaco_espurio_nada_e_consumido():
    assert normalizar_ligaduras(f"{FI_E00B}nal e {FL_E00C}") == "final e fl"


def test_consome_so_um_espaco():
    assert normalizar_ligaduras(f"a{FI_E00B}  b") == "afi b"


def test_texto_sem_ligaduras_e_idempotente():
    texto = "Recurso especial. Art. 14 do CDC: fi e fl normais."
    assert normalizar_ligaduras(texto) == texto
    uma_vez = normalizar_ligaduras(f"a {FI_E00B} b")
    assert normalizar_ligaduras(uma_vez) == uma_vez


def test_pipeline_normaliza_ligaduras_antes_de_anonimizar(client, referencia_humana):
    resposta = client.post(
        "/v1/pipeline/process",
        data={"texto": f"As instituições {FI_E00B} nanceiras respondem.", "referencia_humana": referencia_humana},
    )

    assert resposta.status_code == 200
    assert "instituições financeiras respondem" in resposta.json()["texto_anonimizado"]
