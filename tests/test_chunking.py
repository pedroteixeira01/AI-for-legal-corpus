from app.chunking.service import LegalChunker


def test_chunks_sao_contiguos_com_stride_correto(corpus_juridico):
    chunker = LegalChunker(chunk_size=350, overlap=80)

    chunks = chunker.chunk_text(corpus_juridico)

    assert len(chunks) >= 2
    for anterior, atual in zip(chunks, chunks[1:]):
        assert atual.inicio_char == anterior.inicio_char + chunker.stride


def test_tamanho_do_chunk_bate_com_offsets(corpus_juridico):
    chunker = LegalChunker(chunk_size=350, overlap=80)

    for chunk in chunker.chunk_text(corpus_juridico):
        assert chunk.tamanho == chunk.fim_char - chunk.inicio_char
        assert chunk.tamanho <= chunker.chunk_size


def test_ultimo_chunk_termina_no_fim_do_texto(corpus_juridico):
    chunker = LegalChunker(chunk_size=350, overlap=80)

    chunks = chunker.chunk_text(corpus_juridico)

    assert chunks[-1].fim_char == len(corpus_juridico)


def test_texto_menor_que_chunk_size_gera_um_unico_chunk():
    chunker = LegalChunker(chunk_size=500, overlap=100)
    texto = "Texto curto de teste."

    chunks = chunker.chunk_text(texto)

    assert len(chunks) == 1
    assert chunks[0].texto == texto
