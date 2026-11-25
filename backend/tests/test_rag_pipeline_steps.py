"""Integración de pasos observables con el pipeline RAG/R07."""

from types import SimpleNamespace

from services import rag_pipeline


def test_pipeline_incluye_pasos_operativos_y_suficiencia_r07(monkeypatch):
    fragmentos = [
        {
            "chunk_id": "HTM240-CAT-001_catalogo.pdf_1",
            "score": 0.82,
            "pagina": 2,
            "seccion": "CMP-02",
            "texto": "El caudal nominal de CMP-02 es 8-14 l/min.",
        }
    ]
    suficiencia = {
        "status": "sufficient",
        "requested_items": [{
            "item": "caudal nominal de CMP-02",
            "status": "supported",
            "source_ids": [fragmentos[0]["chunk_id"]],
            "evidence_excerpt": "El caudal nominal de CMP-02 es 8-14 l/min.",
        }],
        "missing_information": [],
    }
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda message, _history: message)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda message: message)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_args: fragmentos)
    monkeypatch.setattr(rag_pipeline, "anadir_notas_de_alcance", lambda _q, chunks, _v: chunks)
    monkeypatch.setattr(rag_pipeline, "evaluar_suficiencia_evidencia", lambda *_args: suficiencia)
    monkeypatch.setattr(rag_pipeline, "fragmentos_con_evidencia_validada", lambda chunks, _suff: chunks)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_args: "prompt")
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda _prompt: "### RESUMEN\nEl caudal nominal es 8-14 l/min.\n\n### FUENTE\n- [F1] HTM240-CAT-001, página 2",
    )
    monkeypatch.setattr(rag_pipeline, "verificar_afirmaciones", lambda *_args: {"status": "not_run", "claims_total": 0, "claims_supported": 0, "claims": []})
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(
            rag_top_k=5,
            rag_evidence_min_score=0.30,
            rag_evidence_high_score=0.65,
            rag_ambiguity_detection_enabled=False,
            rag_evidence_sufficiency_enabled=True,
            rag_claim_verification_enabled=False,
        ),
    )

    resultado = rag_pipeline.armar_respuesta("¿Qué caudal tiene CMP-02?", "V2.0", "mechanic", [])

    assert resultado["evidence_sufficiency"]["status"] == "sufficient"
    assert [step["kind"] for step in resultado["steps"]] == ["checks", "query", "search", "analysis", "conclusion"]
    assert resultado["steps"][0]["title"] == "Comprobaciones previas superadas"
    assert resultado["steps"][2]["fragments"][0]["used"] is True
    assert resultado["steps"][3]["title"] == "Cobertura documental completa"


def test_aclaracion_de_version_muestra_la_comprobacion_que_la_detuvo():
    resultado = rag_pipeline.armar_respuesta("¿Qué significa HTM-0142 en V1.0?", "V2.0", "mechanic", [])

    assert resultado["needs_clarification"] is True
    [paso] = resultado["steps"]
    assert paso["kind"] == "checks"
    assert paso["title"] == "Comprobaciones previas: falta un dato"
    assert [punto["status"] for punto in paso["points"]] == ["ok", "stop"]
    assert "V1.0" in paso["points"][1]["text"]


def test_respuesta_a_aclaracion_aparece_como_aclaracion_aplicada(monkeypatch):
    from types import SimpleNamespace

    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿A cuál te refieres: bomba A (CMP-02) o bomba B (CMP-03)?",
            "clarification_kind": "technical",
        },
    ]
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: [{"chunk_id": "A_1", "score": 0.8}])
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
        rag_ambiguity_detection_enabled=True,
    ))

    resultado = rag_pipeline.armar_respuesta("La bomba A", "V2.0", "mechanic", historial)

    etapas = [etapa["label"] for etapa in resultado["steps"][1]["stages"]]
    assert etapas[:3] == ["Pregunta original", "Aclaración aplicada", "Pregunta completa"]
    assert "Reformulada con el historial" not in etapas
