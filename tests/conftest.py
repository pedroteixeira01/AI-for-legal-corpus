import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.samples import CORPUS_JURIDICO_EXEMPLO, REFERENCIA_HUMANA_GOLD


@pytest.fixture
def corpus_juridico() -> str:
    return CORPUS_JURIDICO_EXEMPLO


@pytest.fixture
def referencia_humana() -> str:
    return REFERENCIA_HUMANA_GOLD


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
