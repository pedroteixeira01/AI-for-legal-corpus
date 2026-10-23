def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pipeline_process_com_texto_bruto_retorna_resultado_completo(client, corpus_juridico, referencia_humana):
    response = client.post(
        "/v1/pipeline/process",
        data={
            "texto": corpus_juridico,
            "referencia_humana": referencia_humana,
            "chunk_size": 350,
            "overlap": 80,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_chunks"] == len(payload["chunks"])
    assert "sumario_sintetizado" in payload
    assert set(payload["metricas_rouge"].keys()) == {"rouge1", "rouge2", "rougeL"}
    assert payload["anonimizacao"]["modo"] in ("presidio_pt", "regex_only")


def test_pipeline_process_sem_texto_e_sem_arquivo_retorna_422(client, referencia_humana):
    response = client.post("/v1/pipeline/process", data={"referencia_humana": referencia_humana})

    assert response.status_code == 422


def test_pipeline_exemplo_retorna_corpus_e_referencia(client):
    response = client.get("/v1/pipeline/exemplo")

    assert response.status_code == 200
    payload = response.json()
    assert "texto" in payload
    assert "referencia_humana" in payload


def test_pipeline_process_usa_o_backend_configurado_e_defaults_do_chunker(client, corpus_juridico, referencia_humana):
    response = client.post(
        "/v1/pipeline/process", data={"texto": corpus_juridico, "referencia_humana": referencia_humana}
    )

    assert response.status_code == 200
    # Corpus de exemplo (~1,4 mil caracteres) cabe em um bloco com o padrão de 3000 caracteres.
    assert response.json()["total_chunks"] == 1
    assert response.json()["sumario_sintetizado"].startswith("SÍNTESE EXECUTIVA")


def test_chunk_com_overlap_maior_que_tamanho_retorna_422(client):
    response = client.post("/v1/chunk", json={"texto": "Texto qualquer.", "chunk_size": 100, "overlap": 100})

    assert response.status_code == 422


def test_pipeline_com_overlap_invalido_retorna_422(client, referencia_humana):
    response = client.post(
        "/v1/pipeline/process",
        data={"texto": "Texto.", "referencia_humana": referencia_humana, "chunk_size": 100, "overlap": 200},
    )

    assert response.status_code == 422


def test_servidor_llm_indisponivel_retorna_503(client, monkeypatch, corpus_juridico, referencia_humana):
    import httpx

    from app.summarization.service import RamalamaSummarizer

    def recusa(request):
        raise httpx.ConnectError("conexão recusada")

    summarizer = RamalamaSummarizer(client=httpx.Client(transport=httpx.MockTransport(recusa)))
    monkeypatch.setattr("app.pipeline.service.get_summarizer", lambda: summarizer)

    response = client.post(
        "/v1/pipeline/process", data={"texto": corpus_juridico, "referencia_humana": referencia_humana}
    )

    assert response.status_code == 503
    assert "ramalama serve" in response.json()["detail"]
