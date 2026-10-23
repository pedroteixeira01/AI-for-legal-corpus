from app.evaluation.service import EvaluatorROUGE


def test_sumarios_identicos_tem_fmeasure_maxima():
    evaluator = EvaluatorROUGE()
    texto = "Recurso conhecido e desprovido por unanimidade de votos."

    metricas = evaluator.calcular_metricas(texto, texto)

    assert metricas["rouge1"]["fmeasure"] == 1.0
    assert metricas["rougeL"]["fmeasure"] == 1.0


def test_metricas_possuem_as_tres_chaves_com_valores_no_intervalo_valido(referencia_humana):
    evaluator = EvaluatorROUGE()
    sumario_gerado = (
        "SÍNTESE EXECUTIVA DO ACÓRDÃO JURÍDICO:\n"
        "1. TESE PRINCIPAL: Reconhecimento da responsabilidade civil objetiva por falha no serviço bancário.\n"
        "2. DANOS MORAIS E MATERIAL: Mantida a condenação por danos morais fixada em R$ 10.000,00.\n"
        "3. DISPOSITIVO: Recurso conhecido e desprovido por unanimidade de votos."
    )

    metricas = evaluator.calcular_metricas(sumario_gerado, referencia_humana)

    for chave in ("rouge1", "rouge2", "rougeL"):
        assert chave in metricas
        for subchave in ("precision", "recall", "fmeasure"):
            valor = metricas[chave][subchave]
            assert 0.0 <= valor <= 1.0


def test_rouge1_fmeasure_maior_ou_igual_a_rouge2(referencia_humana):
    evaluator = EvaluatorROUGE()
    sumario_gerado = (
        "Trata-se de apelação cível envolvendo responsabilidade objetiva de instituição bancária."
    )

    metricas = evaluator.calcular_metricas(sumario_gerado, referencia_humana)

    assert metricas["rouge1"]["fmeasure"] >= metricas["rouge2"]["fmeasure"]


def test_tokenizador_preserva_acentos():
    from app.evaluation.service import TokenizadorUnicode

    assert TokenizadorUnicode().tokenize("apelação cível") == ["apelação", "cível"]
    assert TokenizadorUnicode().tokenize("Súmula 479, R$ 10.000,00") == ["súmula", "479", "r", "10", "000", "00"]


def test_rouge_nao_descarta_letras_acentuadas():
    evaluator = EvaluatorROUGE()

    # Com o tokenizador padrão do rouge-score, "apelação" viraria "apela"+"o" e as palavras
    # acentuadas diferentes ("cível" x "crível") ainda casariam em "c" e "vel".
    metricas = evaluator.calcular_metricas("apelação cível", "apelação crível")

    assert metricas["rouge1"]["fmeasure"] == 0.5


def test_rouge_sem_stemmer():
    evaluator = EvaluatorROUGE()

    metricas = evaluator.calcular_metricas("recursos", "recurso")

    assert metricas["rouge1"]["fmeasure"] == 0.0


CHECKLIST = {
    "tese": ["responsabilidade objetiva"],
    "valores": ["10.000,00", "dez mil reais"],
    "normas": ["sumula 479", "art. 14"],
    "dispositivo": ["desprovido", "negaram provimento", "nega-se provimento"],
}


def test_checklist_todos_os_itens_atendidos():
    from app.evaluation.service import avaliar_checklist

    sintese = (
        "A responsabilidade objetiva do banco, conforme a Súmula 479 do STJ, "
        "levou à manutenção de R$ 10.000,00. Recurso DESPROVIDO."
    )

    resultado = avaliar_checklist(sintese, CHECKLIST)

    assert resultado["itens"] == {"tese": True, "valores": True, "normas": True, "dispositivo": True}
    assert resultado["proporcao"] == 1.0


def test_checklist_qualquer_variante_basta_e_ignora_acentos_caixa_e_espacos():
    from app.evaluation.service import avaliar_checklist

    sintese = "RESPONSABILIDADE   OBJETIVA;  indenização de dez mil  reais;  ARTIGO omitido; Negaram   provimento."

    resultado = avaliar_checklist(sintese, CHECKLIST)

    assert resultado["itens"] == {"tese": True, "valores": True, "normas": False, "dispositivo": True}
    assert resultado["proporcao"] == 0.75


def test_checklist_sintese_vazia_nao_atende_nada():
    from app.evaluation.service import avaliar_checklist

    resultado = avaliar_checklist("", CHECKLIST)

    assert not any(resultado["itens"].values())
    assert resultado["proporcao"] == 0.0


def test_carregar_checklist_valida_formato(tmp_path):
    import json

    import pytest

    from app.evaluation.service import carregar_checklist

    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(CHECKLIST), encoding="utf-8")
    assert carregar_checklist(ok) == CHECKLIST

    ruim = tmp_path / "ruim.json"
    ruim.write_text(json.dumps({"tese": "texto solto"}), encoding="utf-8")
    with pytest.raises(ValueError):
        carregar_checklist(ruim)
