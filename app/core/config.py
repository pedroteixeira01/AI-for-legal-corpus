from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação, carregada de variáveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Metadados da API
    app_name: str = "Pipeline Jurídico NLP"
    app_version: str = "0.1.0"

    # Servidor
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True

    # Chunking (em caracteres, com cortes em fim de frase)
    chunk_size: int = 3000
    chunk_overlap: int = 600

    # Anonimização (LGPD)
    presidio_language: str = "pt"
    spacy_model: str = "pt_core_news_lg"

    # Síntese: 'mock' (texto fixo, sem LLM) ou 'ramalama' (LLM local via API compatível com OpenAI)
    summarizer_backend: Literal["mock", "ramalama"] = "mock"
    ramalama_url: str = "http://localhost:8080"
    ramalama_model: str = "llama3.1:8b"
    llm_temperature: float = 0.1
    llm_seed: int = 42
    llm_num_predict: int = 1024
    llm_num_ctx: int = 16384  # deve ser igual ao `ramalama serve --ctx-size`; só valida/detecta truncamento
    llm_timeout_s: float = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
