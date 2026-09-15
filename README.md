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
(1) Ingestão (PyMuPDF4LLM)
        │
        ▼
(2) Sanitização e Anonimização LGPD (Presidio pt-BR / Regex)
        │
        ▼
(3) Chunking Semântico com Overlap (Pydantic / Window Stride)
        │
        ▼
(4) Síntese de Corpus via LLM (mock — interface pronta para plugar um LLM real)
        │
        ▼
(5) Avaliação Quantitativa (ROUGE Score) ➔ [ Relatório Executivo ]
```

O pipeline é exposto como uma **API FastAPI**, organizada por feature (package-by-feature) com App Factory e rotas versionadas sob `/v1`.

---

## Tecnologias Utilizadas

| Categoria | Tecnologia |
|---|---|
| Linguagem | Python 3.11 ou 3.12 (ver nota abaixo) |
| Framework de API e Validação | FastAPI / Pydantic v2 |
| Configuração | pydantic-settings (`.env`) |
| Ingestão de Documentos | PyMuPDF (`fitz`) / PyMuPDF4LLM |
| Privacidade e LGPD | Microsoft Presidio Analyzer & Anonymizer |
| NLP & Tokenização | spaCy (`pt_core_news_lg`) |
| Métricas de Avaliação | `rouge-score` |
| Testes | pytest / httpx |

> **Nota sobre a versão do Python:** spaCy e Presidio ainda não publicam wheels para as versões mais recentes do Python (ex.: 3.13/3.14). Use um ambiente virtual com **Python 3.11 ou 3.12** para evitar falhas de instalação.

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

### 4. Configurar variáveis de ambiente (opcional)

```bash
cp .env.example .env
```

Ajuste `CHUNK_SIZE`, `CHUNK_OVERLAP`, `PRESIDIO_LANGUAGE`, `SPACY_MODEL`, `HOST`/`PORT` conforme necessário — todos têm defaults sensatos.

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

[2] Chunking Concluído: 5 blocos gerados com sobreposição semântica.
   -> Chunk 0 | Tamanho: 350 chars | Start: 0 End: 350
   -> Chunk 1 | Tamanho: 350 chars | Start: 270 End: 620
   -> Chunk 2 | Tamanho: 350 chars | Start: 540 End: 890
   -> Chunk 3 | Tamanho: 350 chars | Start: 810 End: 1160
   -> Chunk 4 | Tamanho: 332 chars | Start: 1080 End: 1412

[3] Síntese Gerada pelo Modelo:
SÍNTESE EXECUTIVA DO ACÓRDÃO JURÍDICO:
1. TESE PRINCIPAL: Reconhecimento da responsabilidade civil objetiva por falha no serviço bancário...
2. DANOS MORAIS E MATERIAL: Mantida a condenação por danos morais fixada em R$ 10.000,00...
3. DISPOSITIVO: Recurso conhecido e desprovido por unanimidade.

[4] Métricas de Desempenho (ROUGE Score):
   - ROUGE-1 F1-Score: 0.5526
   - ROUGE-2 F1-Score: 0.2933
   - ROUGE-L F1-Score: 0.4079
```

> Estes números diferem dos valores da versão de experimentação original (`main.py` antigo), pois aquela versão rodava com o bug de idioma do Presidio (nenhuma entidade de NER era de fato mascarada). Com o NER em português corrigido, nomes próprios como "Maria dos Santos" e "João da Silva" passam a virar `<PERSON>`, alterando o comprimento do texto sanitizado e, por consequência, o número de chunks e as métricas ROUGE.

---

## Endpoints

Todas as rotas ficam sob o prefixo `/v1`.

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/v1/pipeline/process` | **Endpoint orquestrador** — executa o pipeline completo (ingestão → sanitização → chunking → síntese → ROUGE) |
| `GET` | `/v1/pipeline/exemplo` | Devolve o corpus fictício e a referência-ouro usados na demonstração (útil para montar o `curl` abaixo sem um PDF real) |
| `POST` | `/v1/ingest` | Extrai texto de um PDF (ou aceita texto bruto) |
| `POST` | `/v1/anonymize` | Aplica a anonimização LGPD (Presidio pt-BR + regex) |
| `POST` | `/v1/chunk` | Segmenta um texto em blocos com sobreposição |
| `POST` | `/v1/summarize` | Sintetiza uma lista de chunks (implementação mock) |
| `POST` | `/v1/evaluate` | Calcula as métricas ROUGE-1/2/L entre síntese e referência |
| `GET` | `/health` | Verificação simples de disponibilidade |

Os endpoints por etapa existem para fins didáticos da monografia; o essencial é `POST /v1/pipeline/process`.

---

## Exemplo de Chamada (curl)

### Com texto bruto (sem precisar de um PDF)

```bash
curl -X POST http://127.0.0.1:8000/v1/pipeline/process \
  -F "texto=EMENTA: APELAÇÃO CÍVEL. DIREITO DO CONSUMIDOR. A autora, Maria dos Santos (CPF 987.654.321-11), ajuizou ação declaratória de inexistência de débito. A responsabilidade das instituições financeiras é objetiva, nos termos do Art. 14 do CDC. Dano moral configurado in re ipsa. Quantum mantido em R$ 10.000,00. NEGA-SE PROVIMENTO AO RECURSO." \
  -F "referencia_humana=Apelação cível envolvendo responsabilidade objetiva de instituição bancária, com manutenção da condenação em danos morais de R$ 10.000,00 e desprovimento do recurso." \
  -F "chunk_size=350" \
  -F "overlap=80"
```

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

Cobrem anonimização (mascaramento de CPF, comportamento em modo degradado), chunking (contiguidade e stride dos blocos) e avaliação ROUGE (intervalo de valores, casos triviais), além de testes básicos da API via `TestClient`. Os testes que dependem do modelo spaCy são pulados automaticamente (`skipif`) quando `pt_core_news_lg` não está instalado.

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
│   ├── chunking/            # LegalChunker (sliding window com overlap)
│   ├── summarization/       # BaseSummarizer + mock LegalSummarizerLLM
│   ├── evaluation/          # EvaluatorROUGE
│   ├── pipeline/            # orquestrador do pipeline completo
│   └── api/v1/router.py     # agrega os routers de cada feature sob /v1
├── scripts/
│   └── demo_pipeline.py     # demonstração em linha de comando (fluxo do main.py original)
├── tests/                   # pytest
├── docs/                    # diagramas de arquitetura (D2)
├── main.py                  # ponto de entrada: uvicorn.run(create_app())
├── requirements.txt
├── .env.example
└── README.md
```

---

## Conformidade e Segurança Jurídica

- **LGPD (Lei nº 13.709/2018) & Resolução CNJ nº 615/2025** — Anonimização e mascaramento de dados sensíveis diretamente na origem (*Privacy by Design*), com o `AnalyzerEngine` do Presidio configurado para o idioma português (`pt`) e uma camada complementar de regex para CPF.
- **Diretrizes Proseg-IA (CNJ 2026)** — Ingestão de texto limpo preservando metadados estruturais para mitigação de ataques adversariais por *Prompt Injection*.
