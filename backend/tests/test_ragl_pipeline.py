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
    assert resultado["steps"]


def _fragmento(chunk_id, score, pagina=1):
    return {
        "chunk_id": chunk_id, "score": score, "texto": "Texto del fragmento.",
        "categoria": "Manual", "versiones": ["V1.0"], "pagina": pagina, "seccion": None,
    }


def test_solo_devuelve_las_fuentes_que_el_modelo_ha_utilizado(monkeypatch):
    fragmentos = [
        _fragmento("HTM240-MNT-001_Mantenimiento.pdf_3", 0.8, pagina=4),
        _fragmento("HTM240-DTC-001_Codigos.pdf_7", 0.7),
        _fragmento("HTM240-BOL-006_Boletin.pdf_1", 0.6, pagina=2),
    ]
    respuesta_llm = (
        "### RESUMEN\nCambia el fluido cada 60.000 km.\n\n"
        "### PASOS SEGUIDOS\n"
        "1. Identifiqué que la consulta trata del intervalo de cambio de fluido.\n"
        "2. Comparé F1 con el boletín F3, que corrige el dato.\n\n"
        "### FRAGMENTOS UTILIZADOS\nF1, F3"
    )
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: respuesta_llm)
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))

    resultado = rag_pipeline.armar_respuesta("¿Cada cuánto cambio el fluido?", "V1.0", "mechanic", [])

    assert [fuente["id"] for fuente in resultado["sources"]] == [
        "HTM240-MNT-001_Mantenimiento.pdf_3",
        "HTM240-BOL-006_Boletin.pdf_1",
    ]
    assert resultado["documents_consulted"] == 2
    # El cierre no aparece en el texto de la respuesta.
    assert "PASOS SEGUIDOS" not in resultado["message"]["content"]
    assert "FRAGMENTOS UTILIZADOS" not in resultado["message"]["content"]
    # Pasos por fases: consulta, búsqueda (con cada fragmento), razonamiento y conclusión.
    pasos = {paso["kind"]: paso for paso in resultado["steps"]}
    assert [paso["kind"] for paso in resultado["steps"]] == ["query", "search", "analysis", "conclusion"]
    assert [(f["document"], f["used"]) for f in pasos["search"]["fragments"]] == [
        ("HTM240-MNT-001", True), ("HTM240-DTC-001", False), ("HTM240-BOL-006", True),
    ]
    assert pasos["search"]["fragments"][1]["source_type"] == "dtc_catalog"
    # Las referencias F1/F3 del modelo salen del texto a `refs`, con el documento y la página.
    assert pasos["analysis"]["points"][1] == {
        "text": "Comparé HTM240-MNT-001 con el boletín, que corrige el dato.",
        "refs": ["HTM240-MNT-001 · pág. 4", "HTM240-BOL-006 · pág. 2"],
    }
    assert pasos["conclusion"]["evidence"] == "high"
    assert "2 fragmentos de 2 documentos" in pasos["conclusion"]["detail"]


def test_sin_evidencia_indica_los_pasos_realizados(monkeypatch):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: [{"score": 0.2}])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))

    resultado = rag_pipeline.armar_respuesta("Pregunta", "V1.0", "mechanic", [])

    conclusion = resultado["steps"][-1]
    assert conclusion["kind"] == "conclusion"
    assert conclusion["evidence"] == "insufficient"
    assert "0.20" in conclusion["detail"]
