import pytest

from app.anonymization.service import get_anonymizer

CPF_APELANTE = "123.456.789-00"
CPF_APELADO = "987.654.321-11"


@pytest.fixture(scope="module")
def anonymizer():
    return get_anonymizer()


def test_cpfs_sao_removidos_do_texto(anonymizer, corpus_juridico):
    # Com NER ativo, o Presidio (recognizer BR_CPF) já substitui o CPF por
    # <BR_CPF> antes da regex complementar rodar; em modo degradado, quem
    # cobre o CPF é só a regex ([CPF_OMITIDO]). Em ambos os casos, o número
    # do CPF não pode mais aparecer em texto plano.
    texto_anonimizado = anonymizer.sanitizar(corpus_juridico)

    assert CPF_APELANTE not in texto_anonimizado
    assert CPF_APELADO not in texto_anonimizado
    assert "<BR_CPF>" in texto_anonimizado or "[CPF_OMITIDO]" in texto_anonimizado


def test_regex_complementar_cobre_cpf_mesmo_sem_ner(anonymizer, corpus_juridico, monkeypatch):
    # Força o modo degradado para exercitar isoladamente a camada de regex
    # complementar, independentemente do NER estar disponível no ambiente.
    monkeypatch.setattr(anonymizer, "ner_ativo", False)

    texto_anonimizado = anonymizer.sanitizar(corpus_juridico)

    assert CPF_APELANTE not in texto_anonimizado
    assert CPF_APELADO not in texto_anonimizado
    assert "[CPF_OMITIDO]" in texto_anonimizado


def test_texto_sem_pii_permanece_intacto(anonymizer):
    texto = "O recurso foi conhecido e desprovido por unanimidade de votos."

    texto_anonimizado = anonymizer.sanitizar(texto)

    assert texto_anonimizado == texto


def test_sanitizar_nao_levanta_excecao_em_modo_degradado(anonymizer, corpus_juridico):
    # Independentemente de o modelo spaCy estar instalado ou não, sanitizar()
    # deve sempre retornar uma string, nunca lançar exceção.
    resultado = anonymizer.sanitizar(corpus_juridico)
    assert isinstance(resultado, str)
    assert anonymizer.modo in ("presidio_pt", "regex_only")


@pytest.mark.skipif(not get_anonymizer().ner_ativo, reason="Requer o modelo spaCy pt_core_news_lg instalado")
def test_nomes_proprios_sao_mascarados_quando_ner_ativo(anonymizer, corpus_juridico):
    texto_anonimizado = anonymizer.sanitizar(corpus_juridico)

    assert "Maria dos Santos" not in texto_anonimizado
    assert "João da Silva" not in texto_anonimizado
    assert "<PERSON>" in texto_anonimizado
