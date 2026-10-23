import pytest

from app.chunking.service import LegalChunker, _inicios_de_frase

# ~100 frases curtas, com abreviações e valores monetários, para forçar vários blocos.
FRASE = "O relator Des. João votou pelo desprovimento nos termos do art. 14 do CDC e fixou R$ 10.000,00 de indenização. "
TEXTO_LONGO = "".join(f"{FRASE.rstrip()[:-1]} (item {i}).\n" if i % 7 == 0 else FRASE for i in range(100))


def _palavras(texto: str) -> set[str]:
    return set(texto.split())


def _verifica_limites_de_palavra(texto, chunks):
    for c in chunks:
        assert texto[c.inicio_char : c.fim_char] == c.texto
        assert c.tamanho == len(c.texto)
        # início: começo do texto ou logo após um espaço; fim: fim do texto ou logo após um espaço
        assert c.inicio_char == 0 or texto[c.inicio_char - 1].isspace(), f"bloco {c.chunk_id} começa no meio de palavra"
        assert c.fim_char == len(texto) or texto[c.fim_char - 1].isspace(), f"bloco {c.chunk_id} termina no meio de palavra"


def test_nenhum_bloco_comeca_ou_termina_no_meio_de_palavra():
    for tamanho, overlap in [(300, 60), (500, 0), (777, 200), (1000, 600)]:
        chunks = LegalChunker(tamanho, overlap).chunk_text(TEXTO_LONGO)
        assert len(chunks) > 1
        _verifica_limites_de_palavra(TEXTO_LONGO, chunks)


def test_uniao_dos_blocos_cobre_o_texto_inteiro():
    for overlap in (0, 80):
        chunks = LegalChunker(400, overlap).chunk_text(TEXTO_LONGO)
        assert chunks[0].inicio_char == 0
        assert chunks[-1].fim_char == len(TEXTO_LONGO)
        for anterior, atual in zip(chunks, chunks[1:]):
            assert atual.inicio_char <= anterior.fim_char, "há um buraco entre blocos consecutivos"
        assert [c.chunk_id for c in chunks] == list(range(len(chunks)))


def test_com_sobreposicao_blocos_consecutivos_se_sobrepoem():
    chunks = LegalChunker(400, 100).chunk_text(TEXTO_LONGO)

    assert len(chunks) > 2
    for anterior, atual in zip(chunks, chunks[1:]):
        assert atual.inicio_char < anterior.fim_char
        assert atual.inicio_char > anterior.inicio_char
        assert anterior.fim_char - atual.inicio_char <= 100


def test_sem_sobreposicao_blocos_sao_contiguos():
    chunks = LegalChunker(400, 0).chunk_text(TEXTO_LONGO)

    assert len(chunks) > 2
    for anterior, atual in zip(chunks, chunks[1:]):
        assert atual.inicio_char == anterior.fim_char
    assert "".join(c.texto for c in chunks) == TEXTO_LONGO


def test_blocos_respeitam_o_tamanho_maximo_e_terminam_em_fim_de_frase():
    chunks = LegalChunker(400, 100).chunk_text(TEXTO_LONGO)

    for c in chunks[:-1]:
        assert c.tamanho <= 400
        assert c.tamanho > 200  # corte em frase fica depois de L/2
        assert c.texto.rstrip()[-1] in ".)"


@pytest.mark.parametrize("overlap", [0, 50])
@pytest.mark.parametrize(
    "texto",
    [
        "",
        "   \n ",
        "Texto curto de teste.",
        "palavra " * 300,  # sem pontuação
        "x" * 2500,  # sem espaços
        "a. " * 400,  # só abreviação de uma letra
        "Frase. " * 400,
    ],
    ids=["vazio", "so_espacos", "menor_que_L", "sem_pontuacao", "sem_espacos", "pontos_curtos", "frases"],
)
def test_algoritmo_termina_e_cobre_o_texto(texto, overlap):
    chunks = LegalChunker(200, overlap).chunk_text(texto)

    if not texto.strip():
        assert chunks == []
        return
    assert chunks[0].inicio_char == 0
    assert chunks[-1].fim_char == len(texto)
    for anterior, atual in zip(chunks, chunks[1:]):
        assert atual.inicio_char > anterior.inicio_char  # sempre avança
        assert atual.inicio_char <= anterior.fim_char
    assert all(c.tamanho <= 200 for c in chunks)


def test_texto_menor_que_chunk_size_gera_um_unico_chunk():
    texto = "Texto curto de teste."

    chunks = LegalChunker(500, 100).chunk_text(texto)

    assert len(chunks) == 1
    assert chunks[0].texto == texto
    assert (chunks[0].inicio_char, chunks[0].fim_char) == (0, len(texto))


def test_string_sem_espacos_e_cortada_em_L():
    chunks = LegalChunker(100, 0).chunk_text("x" * 250)

    assert [c.tamanho for c in chunks] == [100, 100, 50]


def test_sem_pontuacao_corta_no_ultimo_espaco():
    texto = "palavra " * 100
    chunks = LegalChunker(100, 0).chunk_text(texto)

    _verifica_limites_de_palavra(texto, chunks)
    assert all(c.tamanho <= 100 for c in chunks)


def test_abreviacao_nao_gera_corte():
    # Sem a regra, "art." e "Des." (seguidos de maiúscula) seriam limites de frase.
    chunker = LegalChunker(70, 0)

    chunks = chunker.chunk_text("Segundo o art. 14 do CDC, o banco responde. Outra frase longa aqui, mesmo assim.")
    assert chunks[0].texto.startswith("Segundo o art. 14 do CDC")
    for c in chunks:
        assert not c.texto.rstrip().endswith("art.")

    chunks = chunker.chunk_text("O relator foi o Des. João da Silva, que votou. O revisor, Min. Pedro, acompanhou o voto.")
    for c in chunks:
        assert not c.texto.rstrip().lower().endswith(("des.", "min."))


def test_art_14_do_cdc_nao_gera_limite_de_frase():
    texto = "Aplica-se o art. 14 do CDC. Também o art. Quatorze, por analogia. Fim."

    inicios = _inicios_de_frase(texto)

    # Só os pontos finais reais abrem frase ("Também" e "Fim"); "art. 14" e "art. Quatorze" não.
    assert [texto[i:].split()[0] for i in inicios] == ["Também", "Fim."]


@pytest.mark.parametrize("abreviacao", ["Art.", "arts.", "Fl.", "FLS.", "n.", "nº.", "Des.", "Min.", "Rel.", "Dr.", "Dra.",
                                        "Sr.", "Sra.", "S.A.", "Ltda.", "inc.", "p.", "cf.", "v.g.", "e.g."])
def test_cada_abreviacao_da_lista_e_ignorada(abreviacao):
    # Com L=40, o único candidato a corte "bom" seria logo depois da abreviação.
    texto = f"Texto inicial do voto {abreviacao} Seguinte frase continua por bastante tempo aqui."
    chunks = LegalChunker(40, 0).chunk_text(texto)

    assert not chunks[0].texto.rstrip().endswith(abreviacao)


def test_ponto_final_normal_e_limite_de_frase():
    texto = "Primeira frase termina aqui. Segunda frase continua por mais um tempo."
    chunks = LegalChunker(50, 0).chunk_text(texto)

    assert chunks[0].texto.rstrip() == "Primeira frase termina aqui."


def test_valores_monetarios_nao_geram_corte():
    # "10.000,00": ponto seguido de dígito, não de espaço + maiúscula.
    texto = "Indenização fixada em R$ 10.000,00 mais correção monetária e juros de mora devidos."
    chunks = LegalChunker(40, 0).chunk_text(texto)

    assert not any(c.texto.rstrip().endswith("10.") for c in chunks)


def test_quebra_de_linha_dupla_e_limite_de_frase():
    texto = "Primeiro parágrafo sem ponto final\n\nSegundo parágrafo vem logo depois, bem longo."
    chunks = LegalChunker(45, 0).chunk_text(texto)

    assert chunks[0].texto.rstrip() == "Primeiro parágrafo sem ponto final"


def test_parametros_invalidos_levantam_erro():
    with pytest.raises(ValueError):
        LegalChunker(0, 0)
    with pytest.raises(ValueError):
        LegalChunker(100, 100)
    with pytest.raises(ValueError):
        LegalChunker(100, -1)


def test_corpus_de_exemplo_e_segmentado_sem_cortar_palavras(corpus_juridico):
    chunks = LegalChunker(350, 80).chunk_text(corpus_juridico)

    assert len(chunks) >= 2
    _verifica_limites_de_palavra(corpus_juridico, chunks)
