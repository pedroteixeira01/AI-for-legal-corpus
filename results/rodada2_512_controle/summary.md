# Resultados do experimento de síntese

- Backend: `ramalama` | modelo: `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF` | arquivo: `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | servidor: `b1-b29c606`
- Chunking: CHUNK_SIZE=3000 caracteres; sobreposição de `blocos_com_sobreposicao` = 600
- Geração: temperature=0.1 | max_tokens=512 | seeds [42, 43, 44]
- Prompts (SHA-256): map `4e6e5a9fcca6` | reduce `ec2d565bb086`
- Execuções por configuração: até 3 (seeds [42, 43, 44]); média ± desvio padrão amostral
- Anonimização: `presidio_pt`

## 1. Corpus

| Documento | Tribunal | Caracteres | Tokens (servidor) | Blocos: inteiro | Blocos: sem sobreposição | Blocos: com sobreposição |
|---|---|---:|---:|---:|---:|---:|
| exemplo_ficticio | TJRJ (fictício) | 8564 | 2608 | 1 | 3 | 4 |
| stj_resp_1101572_rs | STJ | 9102 | 3053 | 1 | 4 | 4 |
| stj_resp_1152764_ce | STJ | 32224 | 9869 | 1 | 12 | 14 |
| stj_resp_1199782_pr | STJ | 29352 | 8911 | 1 | 11 | 12 |
| stj_resp_1213256_rs | STJ | 25651 | 8226 | 1 | 9 | 11 |
| stj_resp_540025_rj | STJ | 19593 | 6217 | 1 | 7 | 8 |
| stj_resp_969129_mg | STJ | 32535 | 10194 | 1 | 12 | 14 |

Caracteres: texto após anonimização (o que o modelo recebe). Tokens: `prompt_tokens` reportado pelo servidor para o prompt *map* do documento inteiro na primeira execução (inclui as instruções do prompt e o template de chat).

## 2. Resultados por configuração (todos os documentos)

| Configuração | Execuções | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | Checklist atendido (%) | Truncamentos suspeitos | Extrações cortadas (length) |
|---|---:|---:|---:|---:|---:|---:|---:|
| inteiro | 21 | 0.327 ± 0.106 | 0.117 ± 0.081 | 0.203 ± 0.080 | 56.7 ± 15.3 | 0 | 1 |
| blocos_sem_sobreposicao | 21 | 0.318 ± 0.082 | 0.109 ± 0.077 | 0.179 ± 0.051 | 48.6 ± 23.8 | 0 | 3 |
| blocos_com_sobreposicao | 21 | 0.340 ± 0.116 | 0.144 ± 0.111 | 0.214 ± 0.098 | 46.9 ± 21.0 | 0 | 7 |

O desvio padrão desta tabela mistura a variação entre documentos e entre seeds; a tabela 3 separa por documento. *Extrações cortadas*: chamadas *map* com `finish_reason = length`, isto é, que bateram em `max_tokens` e podem ter perdido informação.

## 3. Resultados por documento

| Documento | Configuração | Execuções | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | Checklist atendido (%) | Truncamentos suspeitos | Extrações cortadas (length) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| exemplo_ficticio | inteiro | 3 | 0.429 ± 0.014 | 0.201 ± 0.018 | 0.236 ± 0.012 | 50.0 ± 0.0 | 0 | 0 |
| exemplo_ficticio | blocos_sem_sobreposicao | 3 | 0.370 ± 0.050 | 0.175 ± 0.047 | 0.214 ± 0.021 | 33.3 ± 0.0 | 0 | 0 |
| exemplo_ficticio | blocos_com_sobreposicao | 3 | 0.379 ± 0.015 | 0.175 ± 0.019 | 0.227 ± 0.017 | 33.3 ± 0.0 | 0 | 0 |
| stj_resp_1101572_rs | inteiro | 3 | 0.235 ± 0.009 | 0.025 ± 0.001 | 0.157 ± 0.011 | 75.0 ± 0.0 | 0 | 0 |
| stj_resp_1101572_rs | blocos_sem_sobreposicao | 3 | 0.229 ± 0.005 | 0.034 ± 0.005 | 0.140 ± 0.004 | 25.0 ± 0.0 | 0 | 0 |
| stj_resp_1101572_rs | blocos_com_sobreposicao | 3 | 0.200 ± 0.037 | 0.031 ± 0.006 | 0.117 ± 0.021 | 25.0 ± 0.0 | 0 | 0 |
| stj_resp_1152764_ce | inteiro | 3 | 0.171 ± 0.001 | 0.056 ± 0.008 | 0.096 ± 0.002 | 66.7 ± 14.4 | 0 | 0 |
| stj_resp_1152764_ce | blocos_sem_sobreposicao | 3 | 0.230 ± 0.025 | 0.077 ± 0.020 | 0.116 ± 0.007 | 58.3 ± 14.4 | 0 | 0 |
| stj_resp_1152764_ce | blocos_com_sobreposicao | 3 | 0.200 ± 0.016 | 0.054 ± 0.007 | 0.112 ± 0.014 | 58.3 ± 14.4 | 0 | 0 |
| stj_resp_1199782_pr | inteiro | 3 | 0.277 ± 0.015 | 0.067 ± 0.024 | 0.197 ± 0.024 | 58.3 ± 14.4 | 0 | 1 |
| stj_resp_1199782_pr | blocos_sem_sobreposicao | 3 | 0.299 ± 0.047 | 0.070 ± 0.031 | 0.173 ± 0.031 | 83.3 ± 14.4 | 0 | 0 |
| stj_resp_1199782_pr | blocos_com_sobreposicao | 3 | 0.370 ± 0.035 | 0.141 ± 0.050 | 0.233 ± 0.058 | 66.7 ± 14.4 | 0 | 0 |
| stj_resp_1213256_rs | inteiro | 3 | 0.333 ± 0.009 | 0.069 ± 0.020 | 0.159 ± 0.001 | 53.3 ± 11.5 | 0 | 0 |
| stj_resp_1213256_rs | blocos_sem_sobreposicao | 3 | 0.277 ± 0.011 | 0.031 ± 0.009 | 0.147 ± 0.008 | 20.0 ± 0.0 | 0 | 2 |
| stj_resp_1213256_rs | blocos_com_sobreposicao | 3 | 0.270 ± 0.002 | 0.035 ± 0.024 | 0.149 ± 0.003 | 20.0 ± 0.0 | 0 | 0 |
| stj_resp_540025_rj | inteiro | 3 | 0.485 ± 0.054 | 0.229 ± 0.063 | 0.358 ± 0.043 | 60.0 ± 0.0 | 0 | 0 |
| stj_resp_540025_rj | blocos_sem_sobreposicao | 3 | 0.371 ± 0.008 | 0.155 ± 0.023 | 0.204 ± 0.020 | 53.3 ± 11.5 | 0 | 0 |
| stj_resp_540025_rj | blocos_com_sobreposicao | 3 | 0.483 ± 0.031 | 0.296 ± 0.061 | 0.347 ± 0.087 | 66.7 ± 11.5 | 0 | 3 |
| stj_resp_969129_mg | inteiro | 3 | 0.357 ± 0.028 | 0.171 ± 0.014 | 0.220 ± 0.007 | 33.3 ± 14.4 | 0 | 0 |
| stj_resp_969129_mg | blocos_sem_sobreposicao | 3 | 0.449 ± 0.041 | 0.223 ± 0.063 | 0.258 ± 0.043 | 66.7 ± 14.4 | 0 | 1 |
| stj_resp_969129_mg | blocos_com_sobreposicao | 3 | 0.478 ± 0.028 | 0.277 ± 0.071 | 0.313 ± 0.074 | 58.3 ± 14.4 | 0 | 4 |
