# Resultados do experimento

Três rodadas com o mesmo corpus (6 acórdãos do STJ), os mesmos prompts (SHA-256: map `4e6e5a9fcca6`, reduce `ec2d565bb086`) e as mesmas configurações: documento inteiro, blocos de 3.000 caracteres sem sobreposição e blocos de 3.000 caracteres com 600 de sobreposição. Cada configuração foi executada com as seeds 42, 43 e 44, sempre com temperatura 0,1.

- **Modelo:** Llama 3.1 8B Instruct, quantização Q4_K_M (`bartowski/Meta-Llama-3.1-8B-Instruct-GGUF`).
- **Servidor:** RamaLama / llama.cpp, build `b1-b29c606`, `--ctx-size 16384`.

| Pasta | Limite de saída | Papel na análise |
|---|---|---|
| `rodada3_1024_principal/` | 1024 tokens | **Resultado principal.** Nenhuma extração atingiu o limite. |
| `rodada1_512_replicacao/` | 512 tokens | Replicação. As saídas são independentes das rodadas 2 e 3 (nenhuma síntese coincide). |
| `rodada2_512_controle/` | 512 tokens | Controle do efeito do limite de saída. Não entra nas tabelas da monografia. |

## O que cada rodada mostra

**Rodada 3.** É a referência para os números da monografia.

**Rodada 1.** Confirma os achados com saídas diferentes. Oito chamadas da etapa map atingiram o limite de 512 tokens. Nenhuma síntese coincide com as das rodadas 2 e 3, embora o prompt enviado seja o mesmo (as 372 chamadas map têm exatamente os mesmos tokens de entrada). A causa da divergência não foi isolada; a hipótese é uma alteração no cliente entre a rodada 1 e as seguintes.

**Rodada 2.** É idêntica à rodada 3 em todas as 48 sínteses em que nenhum bloco atingiu o limite. As 6 restantes diferem a partir do bloco que foi cortado em 512 tokens. Isso mostra que, com seed, entrada e limite iguais, o servidor reproduz as saídas, e isola o efeito do limite: 3 sínteses passaram a informar corretamente o resultado do julgamento, e nenhum erro grave foi criado ou eliminado. Esta pasta também contém execuções do `exemplo_ficticio`, que foram excluídas da análise. O arquivo bruto foi mantido sem edição.

## Arquivos

- `*/raw.jsonl`: uma linha por execução, com síntese, extrações parciais, ROUGE, checklist, tokens, tempos e `finish_reason` de cada chamada.
- `*/summary.md` e `*/summary.csv`: tabelas geradas pelo `scripts/run_experiment.py`.

## Observações

- **Checklist:** o item "dispositivo" foi retirado do checklist automático e passou a ser avaliado pela revisão manual. Veja o histórico de alterações em `data/experimento/README.md`.
- **Anonimização:** os textos foram anonimizados com Presidio antes de chegar ao modelo, mas a anonimização não é perfeita. No `exemplo_ficticio` da rodada 2, o nome fictício plantado ("Maria dos Santos") aparece em extrações parciais das configurações em blocos. Os nomes de pessoas que restam nas saídas dos acórdãos reais são de ministros e doutrinadores citados nas decisões.