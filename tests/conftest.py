import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.config import get_settings
from app.core.samples import CORPUS_JURIDICO_EXEMPLO, REFERENCIA_HUMANA_GOLD
from app.summarization.service import get_summarizer


@pytest.fixture(autouse=True)
def backend_mock(monkeypatch):
    """Os testes nunca falam com um servidor LLM, mesmo que o .env local peça outro backend."""
    monkeypatch.setenv("SUMMARIZER_BACKEND", "mock")
    get_settings.cache_clear()
    get_summarizer.cache_clear()
    yield
    get_settings.cache_clear()
    get_summarizer.cache_clear()


@pytest.fixture
def corpus_juridico() -> str:
    return CORPUS_JURIDICO_EXEMPLO


@pytest.fixture
def referencia_humana() -> str:
    return REFERENCIA_HUMANA_GOLD


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
