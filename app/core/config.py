from functools import lru_cache

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

    # Chunking (valores padrão da demonstração da monografia)
    chunk_size: int = 350
    chunk_overlap: int = 80

    # Anonimização (LGPD)
    presidio_language: str = "pt"
    spacy_model: str = "pt_core_news_lg"

    # Síntese
    summarizer_model_name: str = "Meta-Llama-3-70B-Instruct-Legal"


@lru_cache
def get_settings() -> Settings:
    return Settings()
