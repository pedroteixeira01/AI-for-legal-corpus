# Corpus do experimento

Seis acórdãos reais e públicos do Superior Tribunal de Justiça, extraídos da Revista de Súmulas do STJ, volume 43 (novembro de 2017), que reproduz na íntegra um precedente formador de cada súmula.

- **Fonte:** <https://www.stj.jus.br/docs_internet/revista/eletronica/stj-revista-sumulas-2017_43.pdf>
- **Data de acesso:** 2026-10-07 (também em cada `metadados.json`)

| Pasta | Processo | Órgão julgador | Relator | Julgamento | Súmula | Tema | Corpo (caracteres) |
|---|---|---|---|---|---|---|---|
| `stj_resp_969129_mg` | REsp 969.129-MG | Segunda Seção | Min. Luis Felipe Salomão | 09/12/2009 | 473 | Seguro habitacional no SFH (venda casada) | 32.917 |
| `stj_resp_1101572_rs` | REsp 1.101.572-RS | Terceira Turma | Min. Nancy Andrighi | 16/11/2010 | 474 | DPVAT: indenização proporcional | 9.131 |
| `stj_resp_1213256_rs` | REsp 1.213.256-RS | Segunda Seção | Min. Luis Felipe Salomão | 28/09/2011 | 475 | Protesto indevido por endossatário | 25.977 |
| `stj_resp_540025_rj` | REsp 540.025-RJ | Terceira Turma | Min. Nancy Andrighi | 14/03/2006 | 478 | Cotas condominiais vs. crédito hipotecário | 19.919 |
| `stj_resp_1199782_pr` | REsp 1.199.782-PR | Segunda Seção | Min. Luis Felipe Salomão | 24/08/2011 | 479 | Fraude bancária e fortuito interno | 29.863 |
| `stj_resp_1152764_ce` | REsp 1.152.764-CE | Primeira Seção | Min. Luiz Fux | 23/06/2010 | 498 | Imposto de renda sobre danos morais | 32.379 |

## Arquivos de cada pasta

| Arquivo | Conteúdo |
|---|---|
| `corpo.txt` | Entrada do modelo: relatório e votos. Não contém a ementa nem o parágrafo do acórdão. |
| `ementa.txt` | Resumo de referência para o ROUGE (ementa oficial). |
| `acordao.txt` | Parágrafo do acórdão (resultado e, nos repetitivos, a tese). Excluído da entrada; guardado por transparência. |
| `metadados.json` | Processo, órgão, relator, datas, súmula, fonte e páginas. Partes e advogados foram omitidos (minimização de dados). |
| `checklist_rascunho.json` | Rascunho do checklist factual. **Revise e renomeie para `checklist.json`**; o script do experimento só lê o nome final. |

O parágrafo do acórdão fica fora do corpo porque, nos recursos repetitivos, ele repete a tese com as mesmas palavras da ementa; mantê-lo deixaria o modelo copiar a referência.

## Tratamento aplicado na extração

Script: `scripts/extrair_revista_sumulas.py`.

1. **Ligaduras tipográficas.** O PDF codifica "fi", "fl", "ff" e "Th" como caracteres de uso privado (U+E000, U+E001, U+E002, U+E00B a U+E00E), ou como U+FB01/U+FB02, seguidos de um espaço espúrio. Sem correção, "financeira" vira " nanceira". Três caracteres isolados (U+E00F a U+E011) correspondem a "(", "-" e ")". Depois da correção, não resta nenhum caractere desse tipo.
2. **Cabeçalhos e numeração.** Remoção dos cabeçalhos da revista ("SUPERIOR TRIBUNAL DE JUSTIÇA", "SÚMULAS - PRECEDENTES", "RSSTJ, a. 9, (43): ...") e dos números de página.
3. **Quebras de linha.** As quebras da diagramação foram desfeitas, cada bloco do PDF vira um parágrafo, e parágrafos que atravessam a página foram reunidos.
4. **Hífens.** Hífens em fim de linha foram mantidos, porque todos os 19 casos encontrados nas seções usadas são legítimos ("conta-corrente", "543-C", "tratando-se").
5. **Correção pontual.** "P ERMANENT E" virou "PERMANENTE" na ementa do REsp 1.101.572-RS (espaçamento de letras da diagramação, conferido no PDF).

## Observações para a análise

- **Contaminação.** Os acórdãos são de 2006 a 2011 e amplamente publicados, então podem estar nos dados de treino do modelo. Como todas as configurações usam o mesmo modelo, a comparação entre elas continua válida, mas isso deve constar como limitação. Incluir 1 ou 2 acórdãos recentes, posteriores ao treinamento, permite verificar o efeito.
- **REsp 969.129-MG.** A seção "Dispositivo" do voto reproduz as teses quase literalmente como estão na ementa, o que tende a inflar o ROUGE desse documento.
- **REsp 1.152.764-CE.** A ementa é longa (cerca de 3.300 caracteres), com lista de precedentes e citação doutrinária. Uma síntese de até 120 palavras tende a ter ROUGE mais baixo nesse caso.
- **REsp 540.025-RJ.** O original grafa "proter rem" (em vez de "propter rem"); o texto foi mantido como está.
- **Checklist.** A verificação é por presença de texto (sem acentos e sem diferenciar maiúsculas). As variantes foram escolhidas para evitar falsos positivos: por exemplo, "provido" está contido em "desprovido", por isso o dispositivo usa expressões como "dar provimento" e "negou provimento". Todos os itens dos rascunhos foram conferidos como presentes no corpo. No REsp 1.199.782-PR, o valor da indenização (R$ 15.000,00) está no corpo, mas não na ementa.
- **Nomes das partes.** Os nomes aparecem no corpo, como no documento público. O pipeline os anonimiza antes de enviar o texto ao modelo, e na monografia só devem aparecer trechos já anonimizados.

## Histórico de alterações do checklist

Alterações feitas nos `checklist.json` **após a primeira rodada** do experimento (`results/`, 54 execuções), a partir da análise dos resultados:

| Documento | Alteração | Motivo |
|---|---|---|
| todos os 6 documentos reais | item `dispositivo` **removido** | As sínteses usam formas como "negação de provimento", ausentes das variantes, então o item quase nunca era marcado. Uma busca por texto também não detecta resultado errado (ex.: "provido" no lugar de "desprovido"). O dispositivo passa a ser avaliado manualmente, fora do checklist automático. |
| `stj_resp_1101572_rs` | item `tese`: acrescentada a variante `tabela de reducao` | Formulação equivalente da tese (redução proporcional pela tabela); aparece em 3 das 9 sínteses deste documento na primeira rodada. |
| `stj_resp_969129_mg` | item `tese_seguro`: acrescentadas as variantes `liberdade de contratar`, `escolher a seguradora` e `nao obrigatoriedade de contratacao de seguro habitacional com o agente` | Formulações equivalentes da tese da venda casada; cada uma aparece em 1 das 9 sínteses deste documento na primeira rodada. |

Critérios:

- **Só entraram variantes de sentido equivalente.** Por exemplo, `invalidade` **não** foi acrescentada ao item `condicao` do DPVAT: "invalidade permanente" é um erro do modelo (o termo correto é "invalidez"), e não uma formulação equivalente.
- **As mudanças valem igualmente para as três configurações** (`inteiro`, `blocos_sem_sobreposicao`, `blocos_com_sobreposicao`), pois o checklist é por documento e não por configuração.
- A primeira rodada foi **reavaliada** com os checklists atuais (`python scripts/rescore.py`, sem chamar o modelo), de modo que as duas rodadas sejam comparáveis. Os resultados originais (`results/raw.jsonl`, `summary.*`) permanecem intocados.
