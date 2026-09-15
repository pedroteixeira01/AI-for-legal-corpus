FROM python:3.12-slim

WORKDIR /workspace

# Dependências de sistema exigidas por PyMuPDF/Presidio/spaCy em builds slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download pt_core_news_lg

CMD ["bash"]
