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
