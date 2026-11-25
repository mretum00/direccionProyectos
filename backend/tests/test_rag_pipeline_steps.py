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
    assert [step["kind"] for step in resultado["steps"]] == ["query", "search", "analysis", "conclusion"]
    assert resultado["steps"][1]["fragments"][0]["used"] is True
    assert resultado["steps"][2]["title"] == "Cobertura documental completa"
