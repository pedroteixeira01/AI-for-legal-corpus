# Processamento e Síntese de Corpus Jurídico

> **Engenharia de Dados e Processamento de Linguagem Natural em Documentação Jurídica de Elevada Densidade**

Este repositório contém a implementação prática da pipeline de **Ingestão**, **Sanitização (LGPD)**, **Chunking Semântico**, **Síntese Automatizada (LLM)** e **Avaliação Quantitativa (Métrica ROUGE)** desenvolvida no âmbito do Trabalho de Conclusão de Curso (TCC).

---

## Sumário

- [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Instalação e Configuração](#️-instalação-e-configuração)
- [Execução do Pipeline](#-execução-do-pipeline)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Conformidade e Segurança Jurídica](#-conformidade-e-segurança-jurídica)

---

## Visão Geral da Arquitetura

O sistema foi arquitetado para transformar documentos jurídicos densos e desestruturados (peças processuais, petições e acórdãos em formato PDF) em sínteses executivas estruturadas e de alta fidelidade semântica, respeitando o princípio de *Privacy by Design*.

```
[ PDF / Acórdão Bruto ]
        │
        ▼
(1) Ingestão Segura (PyMuPDF / Proseg-IA)
        │
        ▼
(2) Sanitização e Anonimização LGPD (Presidio / Regex)
        │
        ▼
(3) Chunking Semântico com Overlap (Pydantic / Window Stride)
        │
        ▼
(4) Síntese de Corpus via LLM (Llama-3 / GPT-4o)
        │
        ▼
(5) Avaliação Quantitativa (ROUGE Score) ➔ [ Relatório Executivo ]
```

---

## Tecnologias Utilizadas

| Categoria | Tecnologia |
|---|---|
| Linguagem | Python 3.10+ |
| Framework de API e Validação | FastAPI / Pydantic v2 (Core em Rust) |
| Ingestão de Documentos | PyMuPDF (`fitz`) / PyMuPDF4LLM |
| Privacidade e LGPD | Microsoft Presidio Analyzer & Anonymizer |
| NLP & Tokenização | spaCy |
| Métricas de Avaliação | `rouge-score` |

---

## Instalação e Configuração

### 1. Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/corpus-juridico-nlp.git
cd corpus-juridico-nlp
```

### 2. Criar e Ativar Ambiente Virtual

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Baixar Modelo de Linguagem em Português (spaCy)

Para suporte avançado à identificação de entidades nomeadas (NER) na LGPD:

```bash
python -m spacy download pt_core_news_lg
```

---

## Execução do Pipeline

Para rodar a demonstração completa da pipeline — anonimização, segmentação por blocos lógicos e cálculo das métricas ROUGE:

```bash
python main.py
```

### Exemplo de Saída no Terminal

```text
#### INICIANDO PIPELINE DE PROCESSAMENTO DE CORPUS JURÍDICO ####

[1] Texto Sanitizado (LGPD - Privacy by Design Executado)
[2] Chunking Concluído: 2 blocos gerados com sobreposição semântica.
-> Chunk 0 | Tamanho: 350 chars | Start: 0 End: 350
-> Chunk 1 | Tamanho: 350 chars | Start: 270 End: 620

[3] Síntese Gerada pelo Modelo:
SÍNTESE EXECUTIVA DO ACÓRDÃO JURÍDICO:
1. TESE PRINCIPAL: Reconhecimento da responsabilidade civil objetiva por falha no serviço bancário...
2. DANOS MORAIS E MATERIAL: Mantida a condenação por danos morais fixada em R$ 10.000,00...
3. DISPOSITIVO: Recurso conhecido e desprovido por unanimidade.

[4] Métricas de Desempenho (ROUGE Score):
- ROUGE-1 F1-Score: 0.6383
- ROUGE-2 F1-Score: 0.4043
- ROUGE-L F1-Score: 0.5745
```

---

## Estrutura do Projeto

```text
.
├── main.py                   # Script principal de execução e experimentação
├── requirements.txt           # Dependências do projeto
├── README.md                  # Documentação do repositório
└── docs/                      # diretório de documentações
```

---

## Conformidade e Segurança Jurídica

- **LGPD (Lei nº 13.709/2018) & Resolução CNJ nº 615/2025** — Anonimização e mascaramento de dados sensíveis diretamente na origem (*Privacy by Design*).
- **Diretrizes Proseg-IA (CNJ 2026)** — Ingestão de texto limpo preservando metadados estruturais para mitigação de ataques adversariais por *Prompt Injection*.
