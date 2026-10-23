import pytest

from app.core.config import Settings


@pytest.fixture
def sem_ambiente(monkeypatch):
    for var in ("LLM_NUM_PREDICT", "LLM_TEMPERATURE", "LLM_SEED", "LLM_NUM_CTX", "CHUNK_SIZE", "CHUNK_OVERLAP"):
        monkeypatch.delenv(var, raising=False)


def test_padroes_da_segunda_rodada(sem_ambiente):
    # _env_file=None: o resultado não pode depender do .env local de quem roda os testes
    settings = Settings(_env_file=None)

    assert settings.llm_num_predict == 1024  # com 512, extrações do map saíam cortadas (finish_reason=length)
    assert (settings.llm_temperature, settings.llm_seed, settings.llm_num_ctx) == (0.1, 42, 16384)
    assert (settings.chunk_size, settings.chunk_overlap) == (3000, 600)


def test_variavel_de_ambiente_sobrescreve_o_padrao(monkeypatch):
    monkeypatch.setenv("LLM_NUM_PREDICT", "512")

    assert Settings(_env_file=None).llm_num_predict == 512


def test_env_example_declara_o_mesmo_padrao_do_codigo():
    from pathlib import Path

    exemplo = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")

    assert "LLM_NUM_PREDICT=1024" in exemplo.splitlines()
