"""Pruebas del flujo RAG sin llamar a Groq ni cargar embeddings reales."""

from types import SimpleNamespace

from services import rag_pipeline


def test_pide_aclaracion_si_no_se_indica_una_version(monkeypatch):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda *_: (_ for _ in ()).throw(AssertionError()))

    resultado = rag_pipeline.armar_respuesta("¿Cómo reviso la bomba?", "", "mechanic", [])

    assert resultado["needs_clarification"] is True
    assert resultado["sources"] == []


def test_no_llama_al_modelo_si_la_evidencia_no_alcanza_el_umbral(monkeypatch):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: [{"score": 0.2}])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: (_ for _ in ()).throw(AssertionError()))

    resultado = rag_pipeline.armar_respuesta("Pregunta", "V1.0", "mechanic", [])

    assert resultado["evidence_status"] == "insufficient"
    assert resultado["sources"] == []
    assert resultado["documents_consulted"] == 0


def test_generacion_con_evidencia_alta_devuelve_fuentes(monkeypatch):
    fragmentos = [{"chunk_id": "DTC-001_1", "score": 0.75}]
    fuentes = [{"id": "DTC-001_1", "document": "HTM240-DTC-001.pdf"}]
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta basada en el manual")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: fuentes)
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))

    resultado = rag_pipeline.armar_respuesta("Pregunta", "V1.0", "mechanic", [])

    assert resultado["evidence_status"] == "high"
    assert resultado["sources"] == fuentes
    assert resultado["documents_consulted"] == 1
    assert resultado["message"]["content"] == "Respuesta basada en el manual"
