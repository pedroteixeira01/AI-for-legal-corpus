# Processamento e Síntese de Corpus Jurídico

> **Engenharia de Dados e Processamento de Linguagem Natural em Documentação Jurídica de Elevada Densidade**

Este repositório contém a implementação prática da pipeline de **Ingestão**, **Sanitização (LGPD)**, **Chunking Semântico**, **Síntese Automatizada (LLM)** e **Avaliação Quantitativa (Métrica ROUGE)** desenvolvida no âmbito do Trabalho de Conclusão de Curso (TCC), exposta como uma **API FastAPI** (Capítulo 4 da monografia).

---

## Sumário

- [Visão Geral da Arquitetura](#visão-geral-da-arquitetura)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Instalação e Configuração](#instalação-e-configuração)
- [Execução da API](#execução-da-api)
- [Endpoints](#endpoints)
- [Exemplo de Chamada (curl)](#exemplo-de-chamada-curl)
- [Testes](#testes)
- [Síntese com LLM local (ramalama)](#síntese-com-llm-local-ramalama)
- [Experimento de síntese](#experimento-de-síntese)
- [Reavaliar uma rodada (rescore)](#reavaliar-uma-rodada-rescore)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Conformidade e Segurança Jurídica](#conformidade-e-segurança-jurídica)
- [Notas de Implementação](#notas-de-implementação)

---

## Visão Geral da Arquitetura

O sistema foi arquitetado para transformar documentos jurídicos densos e desestruturados (peças processuais, petições e acórdãos em formato PDF) em sínteses executivas estruturadas e de alta fidelidade semântica, respeitando o princípio de *Privacy by Design*.

```
[ PDF / Acórdão Bruto ]
        │
        ▼
(1) Ingestão (PyMuPDF4LLM; normaliza ligaduras tipográficas do PDF)
        │
        ▼
(2) Sanitização e Anonimização LGPD (Presidio pt-BR / Regex)
        │
        ▼
(3) Chunking em caracteres com overlap, cortando em fim de frase
        │
        ▼
(4) Síntese map-reduce via LLM local (Llama 3.1 8B no ramalama; backend mock para testes)
        │
        ▼
(5) Avaliação Quantitativa (ROUGE Score) ➔ [ Relatório Executivo ]
```

O pipeline é exposto como uma **API FastAPI**, organizada por feature (package-by-feature) com App Factory e rotas versionadas sob `/v1`.

---

## Tecnologias Utilizadas

| Categoria | Tecnologia |
|---|---|
| Linguagem | Python 3.12 (dev container); 3.11 também suportado (ver nota abaixo) |
| Framework de API e Validação | FastAPI / Pydantic v2 |
| Configuração | pydantic-settings (`.env`) |
| Ingestão de Documentos | PyMuPDF (`fitz`) / PyMuPDF4LLM |
| Privacidade e LGPD | Microsoft Presidio Analyzer & Anonymizer |
| NLP & Tokenização | spaCy (`pt_core_news_lg`) |
| LLM (síntese) | Llama 3.1 8B Instruct, **quantizado em Q4_K_M** (bartowski/Meta-Llama-3.1-8B-Instruct-GGUF, Hugging Face), servido pelo [ramalama](https://ramalama.ai) (llama.cpp, API compatível com OpenAI) e chamado por HTTP com `httpx` |
| Métricas de Avaliação | `rouge-score` (tokenizador Unicode, sem stemmer) + checklist factual |
| Testes | pytest / httpx |

> **Nota sobre a versão do Python:** o dev container usa Python 3.12. As dependências (spaCy, Presidio) costumam demorar a publicar wheels para versões novas do Python; a suíte de testes chegou a passar em 3.14 com as versões disponíveis na última verificação, mas, se a instalação falhar, use um ambiente virtual com **Python 3.11 ou 3.12**.

---

## Instalação e Configuração

### 1. Criar e Ativar Ambiente Virtual

```bash
# Linux / macOS (use python3.11 ou python3.12 explicitamente)
python3.12 -m venv venv
source venv/bin/activate

# Windows
py -3.12 -m venv venv
.\venv\Scripts\activate
```

### 2. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 3. Baixar o Modelo de Linguagem em Português (spaCy)

Necessário para a identificação de entidades nomeadas (NER — pessoas, e-mails, telefones) na etapa de anonimização:

```bash
python -m spacy download pt_core_news_lg
```

> **Modo degradado:** se este modelo não estiver instalado, a API sobe normalmente, mas registra um `WARNING` no log e a anonimização passa a usar **somente a camada de regex** (ainda cobre CPFs no padrão `XXX.XXX.XXX-XX`). O campo `anonimizacao.modo` na resposta do pipeline indica `"presidio_pt"` (NER ativo) ou `"regex_only"` (degradado).

### 4. Instalar o ramalama e subir o modelo (somente para a síntese real)

A API e os testes funcionam sem servidor LLM (backend `mock`). Para a síntese com LLM e para o experimento, instale o [ramalama](https://ramalama.ai) (requer Podman ou Docker) e sirva o Llama 3.1 8B Instruct:

```bash
ramalama serve --ctx-size 16384 hf://bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
# API em http://localhost:8080 (baixa o modelo, ~4,9 GB, na primeira execução)
```

O modelo é o **Llama 3.1 8B Instruct na versão quantizada Q4_K_M** (4 bits), publicada pelo [bartowski no Hugging Face](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF), e **não** o modelo em precisão total. Essa é a configuração usada nos resultados do experimento, e o script registra, em cada linha do `raw.jsonl`, o modelo, o arquivo GGUF e o build do servidor, lidos do próprio servidor.

O tamanho do contexto é definido **no servidor** (`--ctx-size`) e deve ser igual a `LLM_NUM_CTX` (veja abaixo). Mantenha o servidor rodando em outro terminal enquanto roda a API ou o experimento.

> **Dev container (podman rootless):** o `ramalama serve` escuta só em `127.0.0.1` do host, que o container não alcança (`Connection refused`). O `.devcontainer/devcontainer.json` usa `--network=pasta:--map-host-loopback,10.0.2.2` para expor o loopback do host em `host.containers.internal`, e define `RAMALAMA_URL=http://host.containers.internal:8080` só dentro do container (o `.env` continua com `localhost`, válido no host). `--network=host` também alcança o servidor, mas, com o podman rootless, a abertura do dev container ficou parada em *Container started* (VS Code Dev Containers 0.469), então não é usado. Depois de alterar o `runArgs`, rode *Dev Containers: Rebuild Container*.

### 5. Configurar variáveis de ambiente (opcional)

```bash
cp .env.example .env
```

Todas as variáveis têm defaults sensatos:

| Variável | Padrão | Descrição |
|---|---|---|
| `SUMMARIZER_BACKEND` | `mock` | `mock` (texto fixo) ou `ramalama` (LLM local) |
| `RAMALAMA_URL` | `http://localhost:8080` | endereço do `ramalama serve` |
| `RAMALAMA_MODEL` | `llama3.1:8b` | nome enviado na requisição; o llama.cpp o ignora. O modelo **realmente servido** (nome, arquivo GGUF/quantização, build, `n_ctx`) é lido de `/v1/models` e `/props` e gravado no `raw.jsonl` e no `summary.md` |
| `LLM_TEMPERATURE` | `0.1` | temperatura de amostragem |
| `LLM_SEED` | `42` | seed (o experimento usa `LLM_SEED`, `+1`, `+2`, …) |
| `LLM_NUM_PREDICT` | `1024` | máximo de tokens gerados por chamada (`max_tokens`). Com 512, extrações do *map* saíam cortadas (`finish_reason = length`); a segunda rodada usa 1024 em todas as configurações. **Atenção:** um `LLM_NUM_PREDICT` no seu `.env` sobrescreve este padrão |
| `LLM_NUM_CTX` | `16384` | contexto do servidor, em tokens: **deve ser igual ao `--ctx-size`** do `ramalama serve`; usado para detectar truncamento |
| `LLM_TIMEOUT_S` | `600` | timeout de cada chamada ao servidor |
| `CHUNK_SIZE` | `3000` | tamanho alvo de cada bloco, em caracteres |
| `CHUNK_OVERLAP` | `600` | sobreposição entre blocos, em caracteres |
| `PRESIDIO_LANGUAGE`, `SPACY_MODEL`, `HOST`, `PORT`, `RELOAD` | ver `.env.example` | anonimização e servidor |

---

## Execução da API

```bash
python main.py
# ou, equivalentemente:
uvicorn app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

A documentação interativa (Swagger UI) fica disponível em `http://127.0.0.1:8000/docs`.

### Demonstração em linha de comando (sem subir a API)

O fluxo original do protótipo (`main.py` de experimentação) foi preservado em `scripts/demo_pipeline.py`, útil para inspecionar rapidamente a saída de cada etapa no terminal:

```bash
python scripts/demo_pipeline.py
```

```text
#### INICIANDO PIPELINE DE PROCESSAMENTO DE CORPUS JURÍDICO ####

[1] Texto Sanitizado (LGPD - Privacy by Design Executado, modo=presidio_pt)

[2] Chunking Concluído: 7 blocos gerados com sobreposição semântica.
   -> Chunk 0 | Tamanho: 313 chars | Start: 0 End: 313
   -> Chunk 1 | Tamanho: 246 chars | Start: 266 End: 512
   -> Chunk 2 | Tamanho: 278 chars | Start: 443 End: 721
   -> Chunk 3 | Tamanho: 302 chars | Start: 646 End: 948
   -> Chunk 4 | Tamanho: 264 chars | Start: 873 End: 1137
   -> Chunk 5 | Tamanho: 318 chars | Start: 1059 End: 1377
   -> Chunk 6 | Tamanho: 112 chars | Start: 1300 End: 1412

[3] Síntese Gerada pelo Modelo:
SÍNTESE EXECUTIVA DO ACÓRDÃO JURÍDICO:
1. TESE PRINCIPAL: Reconhecimento da responsabilidade civil objetiva por falha no serviço bancário...
2. DANOS MORAIS E MATERIAL: Mantida a condenação por danos morais fixada em R$ 10.000,00...
3. DISPOSITIVO: Recurso conhecido e desprovido por unanimidade.

[4] Métricas de Desempenho (ROUGE Score):
   - ROUGE-1 F1-Score: 0.5116
   - ROUGE-2 F1-Score: 0.2677
   - ROUGE-L F1-Score: 0.4031
```

> A demonstração usa o backend `mock`: a síntese é um texto fixo que não lê os blocos, então estes números **não** representam nenhum modelo. Os resultados reais vêm do [experimento](#experimento-de-síntese). O demo usa blocos de 350 caracteres (sobreposição de 80) só para que o corpus de exemplo, que é curto, gere vários blocos.

---

## Endpoints

Todas as rotas ficam sob o prefixo `/v1`.

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/v1/pipeline/process` | **Endpoint orquestrador** — executa o pipeline completo (ingestão → sanitização → chunking → síntese → ROUGE) |
| `GET` | `/v1/pipeline/exemplo` | Devolve o corpus fictício e a referência-ouro usados na demonstração (útil para montar o `curl` abaixo sem um PDF real) |
| `POST` | `/v1/ingest` | Extrai texto de um PDF (ou aceita texto bruto) |
| `POST` | `/v1/anonymize` | Aplica a anonimização LGPD (Presidio pt-BR + regex) |
| `POST` | `/v1/chunk` | Segmenta um texto em blocos com sobreposição, cortando em fim de frase |
| `POST` | `/v1/summarize` | Sintetiza uma lista de chunks com o backend configurado (`mock` ou `ramalama`) |
| `POST` | `/v1/evaluate` | Calcula as métricas ROUGE-1/2/L entre síntese e referência |
| `GET` | `/health` | Verificação simples de disponibilidade |

Os endpoints por etapa existem para fins didáticos da monografia; o essencial é `POST /v1/pipeline/process`. Com `SUMMARIZER_BACKEND=ramalama`, uma falha do servidor (fora do ar, contexto excedido, timeout) devolve `503` com a causa na mensagem.

---

## Exemplo de Chamada (curl)

### Com texto bruto (sem precisar de um PDF)

```bash
curl -X POST http://127.0.0.1:8000/v1/pipeline/process \
  -F "texto=EMENTA: APELAÇÃO CÍVEL. DIREITO DO CONSUMIDOR. A autora, Maria dos Santos (CPF 987.654.321-11), ajuizou ação declaratória de inexistência de débito. A responsabilidade das instituições financeiras é objetiva, nos termos do Art. 14 do CDC. Dano moral configurado in re ipsa. Quantum mantido em R$ 10.000,00. NEGA-SE PROVIMENTO AO RECURSO." \
  -F "referencia_humana=Apelação cível envolvendo responsabilidade objetiva de instituição bancária, com manutenção da condenação em danos morais de R$ 10.000,00 e desprovimento do recurso." \
  -F "chunk_size=500" \
  -F "overlap=100"
```

### Com um acórdão do experimento

O `-F "campo=<arquivo"` do curl envia o conteúdo do arquivo como texto (a ementa, que é a referência do ROUGE, vem do próprio acórdão):

```bash
curl -X POST http://127.0.0.1:8000/v1/pipeline/process \
  -F "texto=<data/experimento/stj_resp_1101572_rs/corpo.txt" \
  -F "referencia_humana=<data/experimento/stj_resp_1101572_rs/ementa.txt"
```

Com `SUMMARIZER_BACKEND=mock` (padrão) a síntese é o texto fixo; com `ramalama`, o map-reduce roda de verdade (um acórdão de ~30 mil caracteres gera cerca de uma dúzia de chamadas).

### Com upload de PDF

```bash
curl -X POST http://127.0.0.1:8000/v1/pipeline/process \
  -F "file=@acordao.pdf;type=application/pdf" \
  -F "referencia_humana=Trata-se de apelação cível em ação declaratória de inexistência de débito..."
```

A resposta é um `PipelineExecutionResult` com o texto original, o texto anonimizado, os chunks gerados, a síntese e as métricas ROUGE — o mesmo schema produzido pelo `main.py` original, agora em Pydantic v2 e com o bloco `anonimizacao` indicando o modo de operação.

---

## Testes

```bash
pytest -v
```

Cobrem anonimização (mascaramento de CPF, comportamento em modo degradado), chunking (cortes em fim de frase, abreviações, sobreposição, terminação), avaliação (ROUGE com acentos, checklist factual), síntese (map-reduce, truncamento, erros do servidor) e o script do experimento, além de testes da API via `TestClient`.

Os testes **não precisam de servidor LLM e não fazem chamadas de rede**: o backend é forçado para `mock` e o `RamalamaSummarizer` é testado contra um servidor simulado (`httpx.MockTransport`). Os testes que dependem do modelo spaCy são pulados automaticamente (`skipif`) quando `pt_core_news_lg` não está instalado. Eles usam o acórdão fictício `data/experimento/exemplo_ficticio/`, que **deve permanecer na pasta**.

---

## Síntese com LLM local (ramalama)

Com `SUMMARIZER_BACKEND=ramalama`, o `RamalamaSummarizer` (`app/summarization/service.py`) faz **map-reduce** chamando `POST {RAMALAMA_URL}/v1/chat/completions` (API compatível com OpenAI do llama.cpp), com a instrução como única mensagem `user`:

1. **Map:** uma chamada por bloco, com `app/summarization/prompts/map.txt`, extrai tese, fundamentos, valores e dispositivo.
2. **Reduce:** uma chamada com as extrações numeradas, com `app/summarization/prompts/reduce.txt`, redige a síntese final (um parágrafo, até 120 palavras).

Mesmo com um único bloco, map + reduce são executados, para que todas as configurações usem exatamente os mesmos prompts. Os prompts são versionados e lidos em tempo de execução.

Cada requisição envia `temperature`, `seed` e `max_tokens` (`LLM_NUM_PREDICT`, padrão 1024) e `cache_prompt: false` (extensão do llama.cpp, para que contagem de tokens e saída não dependam da chamada anterior). Por chamada, são registrados `prompt_tokens`, `completion_tokens`, `finish_reason` e o tempo de parede.

**Contexto e truncamento:** o contexto é fixado no servidor (`--ctx-size`), não por requisição. Se o prompt exceder o contexto, o servidor devolve erro (reportado com mensagem clara). Se `prompt_tokens` chegar a 95% ou mais de `LLM_NUM_CTX`, a execução emite um aviso e é marcada com `truncamento_suspeito: true`. Um `finish_reason` igual a `length` indica saída cortada em `LLM_NUM_PREDICT`.

---

## Experimento de síntese

`scripts/run_experiment.py` compara três configurações por documento, cada uma repetida `--runs` vezes (padrão 3, seeds 42, 43 e 44):

| Configuração | Entrada do modelo |
|---|---|
| `inteiro` | o documento todo como um único bloco |
| `blocos_sem_sobreposicao` | blocos de `CHUNK_SIZE` caracteres, sobreposição 0 |
| `blocos_com_sobreposicao` | blocos de `CHUNK_SIZE` caracteres, sobreposição `CHUNK_OVERLAP` |

A síntese é comparada com a **ementa oficial** (ROUGE-1/2/L, tokenizador que preserva acentos e sem stemmer) e com um **checklist factual** por documento. A entrada do modelo é o corpo do acórdão **sem a ementa**, anonimizado com o mesmo serviço da API.

### Preparar os dados

Crie uma pasta por acórdão em `data/experimento/<doc_id>/` com `corpo.txt`, `ementa.txt`, `checklist.json` e `metadados.json`. O formato está em [`data/experimento/README.md`](data/experimento/README.md). Cada documento precisa gerar pelo menos 3 blocos com `CHUNK_SIZE` (o script aborta antes de começar, se algum não gerar). Os acórdãos reais do experimento (STJ) foram extraídos da Revista de Súmulas do STJ, v. 43, com `python scripts/extrair_revista_sumulas.py <revista_v43.pdf> data/experimento`, que gera `corpo.txt`, `ementa.txt`, `acordao.txt` (parágrafo do julgamento, fora da entrada do modelo) e `metadados.json`; o `checklist.json` é escrito à mão por documento.

A pasta `exemplo_ficticio/` é um acórdão **fictício**, usado nos testes e para validar o fluxo; **não a apague**. No lote real, liste os acórdãos reais em `--docs`, para que o fictício não entre nas médias.

### Reproduzir

```bash
# Documentos reais do experimento (sem o exemplo fictício)
DOCS="stj_resp_1101572_rs stj_resp_1152764_ce stj_resp_1199782_pr stj_resp_1213256_rs stj_resp_540025_rj stj_resp_969129_mg"

# 1. Validar o fluxo sem servidor LLM (resultados em results/mock/, sem valor científico)
python scripts/run_experiment.py --backend mock --runs 1 --docs $DOCS

# 2. Lote real (o `ramalama serve` da seção de instalação rodando em outro terminal).
#    Grave cada rodada na sua própria pasta, para não misturar nem sobrescrever resultados:
python scripts/run_experiment.py --docs $DOCS --out results/rodada3_1024_principal

# Se o lote for interrompido (pode levar horas), retome de onde parou:
python scripts/run_experiment.py --docs $DOCS --out results/rodada3_1024_principal --resume

# Outro número de repetições:
python scripts/run_experiment.py --docs $DOCS --out results/teste --runs 5
```

Antes de rodar, confira que o seu `.env` não fixa um `LLM_NUM_PREDICT` diferente do pretendido: ele sobrescreve o padrão (1024). O script imprime `max_tokens=...` na primeira linha e o grava em cada linha do `raw.jsonl` e no cabeçalho do `summary.md`.

**Rodadas já executadas** (detalhes em [`results/README.md`](results/README.md)): três rodadas com o mesmo corpus, prompts, chunking e seeds, que diferem no `max_tokens` (512 nas rodadas 1 e 2, 1024 na rodada 3, a principal). Com 512, algumas extrações do *map* saem cortadas (`finish_reason = length`), o que o `summary.md` conta na coluna "Extrações cortadas".

Saídas em `--out` (padrão `results/`; as do backend `mock` ficam em `results/mock/` se `--out` for omitido):

- `raw.jsonl`: uma linha por execução (síntese, extrações parciais, ROUGE com precisão/recall/F1, checklist, tokens, tempo, `truncamento_suspeito`) e as condições da execução: `modelo`, `modelo_arquivo`, `servidor_build`, `temperature`, `max_tokens`, `seed` e o SHA-256 dos prompts (`prompt_map_sha256`, `prompt_reduce_sha256`). Escrito a cada execução, então nada se perde se o lote cair.
- `summary.csv`: médias e desvios por documento e configuração (mais as linhas `TODOS`).
- `summary.md`: tabela do corpus (tokens conforme o servidor e blocos por configuração), resultados por configuração (média ± desvio padrão do F1, % do checklist e **extrações cortadas**, isto é, chamadas *map* com `finish_reason = length`) e a mesma tabela por documento.

Ao final do lote, se houver chamadas com `finish_reason = length`, o script lista documento, configuração, seed e bloco de cada uma. O `--resume` recusa continuar se o `raw.jsonl` foi gerado com outro modelo, `max_tokens`, temperatura, versão dos prompts ou `CHUNK_SIZE`/`CHUNK_OVERLAP`, para não misturar condições. Sem `--resume`, o script não sobrescreve um `raw.jsonl` existente.

---

## Reavaliar uma rodada (rescore)

`scripts/rescore.py` recalcula a avaliação de uma rodada **já executada**, sem chamar o modelo, e não modifica o `raw.jsonl`:

```bash
python scripts/rescore.py --raw results/<rodada>/raw.jsonl --out results/<rodada>_reavaliada
```

- **Checklist:** recalculado com os `checklist.json` **atuais** de `data/experimento/` (ver o histórico de alterações em [`data/experimento/README.md`](data/experimento/README.md)).
- **ROUGE:** recalculado com o mesmo avaliador e conferido contra o valor gravado no `raw.jsonl`; divergências acima de 0,0001 são avisadas.

Saídas em `--out`: `summary.md` e `summary.csv` com (1) a tabela por configuração (média e desvio padrão de ROUGE-1/2/L F1, % do checklist e extrações cortadas), (2) a mesma tabela por documento e (3) as **diferenças pareadas** de ROUGE-1 F1 por documento (média das seeds) entre `blocos_com_sobreposicao − blocos_sem_sobreposicao` e `inteiro − blocos_com_sobreposicao`, com a média, o número de documentos a favor e o valor de cada documento.

---

## Estrutura do Projeto

```text
.
├── app/
│   ├── __init__.py          # create_app() — App Factory
│   ├── core/
│   │   ├── config.py        # Settings via pydantic-settings (.env)
│   │   └── samples.py       # corpus de exemplo e referência-ouro
│   ├── ingestion/           # extração de texto de PDF (PyMuPDF4LLM)
│   ├── anonymization/       # LGPDAnonymizer (Presidio pt-BR + regex)
│   ├── chunking/            # LegalChunker (blocos em caracteres, cortes em fim de frase)
│   ├── summarization/       # BaseSummarizer, MockSummarizer, RamalamaSummarizer (map-reduce)
│   │   └── prompts/         # map.txt e reduce.txt (versionados)
│   ├── evaluation/          # EvaluatorROUGE (sem stemmer) + checklist factual
│   ├── pipeline/            # orquestrador do pipeline completo
│   └── api/v1/router.py     # agrega os routers de cada feature sob /v1
├── data/experimento/        # um subdiretório por acórdão: 6 reais do STJ + exemplo_ficticio (ver o README da pasta)
├── results/                 # uma pasta por rodada (raw.jsonl, summary.csv, summary.md) + README.md com a análise
├── scripts/
│   ├── demo_pipeline.py     # demonstração em linha de comando (fluxo do main.py original)
│   ├── run_experiment.py    # experimento: 3 configurações x N repetições, ROUGE + checklist
│   ├── rescore.py           # reavalia uma rodada já executada (checklist atual + ROUGE)
│   └── extrair_revista_sumulas.py  # extrai os acórdãos da Revista de Súmulas do STJ para data/experimento/
├── tests/                   # pytest (API, chunking, ingestão, síntese, avaliação, experimento, rescore)
├── .devcontainer/           # dev container (podman rootless; alcança o ramalama do host)
├── docs/                    # diagramas de arquitetura (D2/SVG)
├── main.py                  # ponto de entrada: uvicorn.run(create_app())
├── requirements.txt
├── .env.example
└── README.md
```

---

## Conformidade e Segurança Jurídica

- **LGPD (Lei nº 13.709/2018) & Resolução CNJ nº 615/2025** — Anonimização e mascaramento de dados sensíveis diretamente na origem (*Privacy by Design*), com o `AnalyzerEngine` do Presidio configurado para o idioma português (`pt`) e uma camada complementar de regex para CPF.
- **Diretrizes Proseg-IA (CNJ 2026)** — Ingestão de texto limpo preservando metadados estruturais para mitigação de ataques adversariais por *Prompt Injection*.

---

## Notas de Implementação

- **Chunking:** blocos de `CHUNK_SIZE` caracteres que terminam no último limite de frase após a metade do bloco (`. ; ! ?` ou quebra de linha, seguidos de espaço e maiúscula, ou de nova linha), sem tratar como fim de frase as abreviações jurídicas comuns (`art.`, `fls.`, `des.`, `min.`, `s.a.` etc.). Sem limite de frase, corta no último espaço; sem espaços, em `CHUNK_SIZE`. O bloco seguinte começa em `fim - CHUNK_OVERLAP`, avançado até o início da próxima frase, e o início sempre avança, então o algoritmo termina para qualquer entrada.
- **ROUGE:** o tokenizador padrão do `rouge-score` descarta letras acentuadas ("apelação" vira "apela" + "o"); por isso o avaliador usa um tokenizador próprio (`\w+` em Unicode, minúsculas) e não usa o stemmer inglês.
- **Reprodutibilidade:** cada linha do `raw.jsonl` registra o modelo realmente servido (arquivo GGUF, build do servidor, `n_ctx`), `temperature`, `max_tokens`, `seed` e o SHA-256 dos prompts, e o `--resume` recusa misturar condições diferentes. A API do llama.cpp é chamada com `cache_prompt: false`, para que a saída não dependa da chamada anterior.
- **Ligaduras de PDF:** alguns PDFs codificam "fi", "fl", "ff" e "Th" como caracteres de uso privado seguidos de um espaço espúrio ("instituições \ue00b nanceiras"); `normalizar_ligaduras` (em `app/ingestion/`) as converte antes da anonimização.
- **Anonimização:** o spaCy marca entidades `MISC`, que o Presidio não mapeia e que não são anonimizadas; elas são ignoradas na configuração para não gerar um aviso por ocorrência (o resultado da anonimização não muda).
- **Limitações:** o modelo é a versão quantizada Q4_K_M do Llama 3.1 8B Instruct, não a de precisão total; a anonimização (NER) não é perfeita, e nomes podem sobrar nas saídas (veja as observações em [`results/README.md`](results/README.md)); o backend `mock` devolve um texto fixo e só serve para validar o fluxo.
