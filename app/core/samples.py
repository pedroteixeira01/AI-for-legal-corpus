"""Corpus de exemplo utilizado na demonstração, nos testes e na documentação.

Acórdão fictício de elevada densidade textual, com dados pessoais plantados
propositalmente para exercitar a camada de anonimização (LGPD).
"""
CORPUS_JURIDICO_EXEMPLO = """
    PODER JUDICIÁRIO DO ESTADO DO RIO DE JANEIRO - TRIBUNAL DE JUSTIÇA
    APELAÇÃO CÍVEL Nº 0012345-67.2024.8.19.0001. RELATOR: DES. JOÃO DA SILVA.
    APELANTE: BANCO EXEMPLO S.A. (CPF/CNPJ REPRESENTANTE: 123.456.789-00).
    APELADO: MARIA DOS SANTOS (CPF: 987.654.321-11).

    EMENTA: APELAÇÃO CÍVEL. DIREITO DO CONSUMIDOR. OPERAÇÕES BANCÁRIAS NÃO RECONHECIDAS.
    FRAUDE PRATICADA POR TERCEIROS. RESPONSABILIDADE OBJETIVA DA INSTITUIÇÃO FINANCEIRA.
    SÚMULA 479 DO SUPERIOR TRIBUNAL DE JUSTIÇA. IN FORTUITO INTERNO.
    A autora, senhora Maria dos Santos, ajuizou ação declaratória de inexistência de débito c/c indenizatória,
    alegando ter sofrido descontos indevidos em sua conta corrente relativos a empréstimo não contratado.
    A instituição financeira apelante sustenta a regularidade das transações e a culpa exclusiva de terceiro.
    Oportuno registrar que a responsabilidade das instituições financeiras é objetiva, nos termos do Art. 14 do CDC.
    O risco do empreendimento abrange as fraudes praticadas por terceiros, configurando fortuito interno.
    Dano moral configurado in re ipsa ante os transtornos causados à parte autora.
    Quantum indenizatório mantido em R$ 10.000,00 (dez mil reais), atendendo aos princípios da razoabilidade e proporcionalidade.
    Restituição em dobro dos valores indevidamente descontados na forma do parágrafo único do art. 42 do CDC.
    NEGA-SE PROVIMENTO AO RECURSO.
    """

# Referência humana para avaliação da métrica ROUGE.
REFERENCIA_HUMANA_GOLD = (
    "Trata-se de apelação cível em ação declaratória de inexistência de débito contra instituição bancária por fraude. "
    "A responsabilidade do banco é objetiva conforme o CDC e a Súmula 479 do STJ. "
    "Foi mantida a condenação em danos morais de R$ 10.000,00 e a restituição em dobro dos valores. "
    "Recurso conhecido e desprovido."
)
