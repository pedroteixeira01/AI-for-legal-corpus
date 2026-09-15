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
