"""Pruebas del flujo RAG sin llamar a Groq ni cargar embeddings reales."""

from types import SimpleNamespace

from services import rag_pipeline


def test_pide_aclaracion_si_no_se_indica_una_version(monkeypatch):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda *_: (_ for _ in ()).throw(AssertionError()))

    resultado = rag_pipeline.armar_respuesta("¿Cómo reviso la bomba?", "", "mechanic", [])

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "engine_version"
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
    assert resultado["safety_alerts"] == []


def test_evidencia_usa_la_mayor_similitud_semantica_y_no_el_primer_ranking(monkeypatch):
    # El primer fragmento aparece primero por una bonificación de ordenación,
    # pero el segundo tiene mayor similitud coseno pura.
    fragmentos = [
        {
            "chunk_id": "HTM240-DTC-001_Catalogo_DTC.pdf_1",
            "score": 0.38,
            "ranking_score": 0.78,
        },
        {
            "chunk_id": "HTM240-DIA-001_Manual_diagnostico.pdf_3",
            "score": 0.72,
            "ranking_score": 0.72,
        },
    ]
    assert fragmentos[0]["ranking_score"] > fragmentos[1]["ranking_score"]
    assert fragmentos[0]["score"] < fragmentos[1]["score"]

    fuentes = [
        {"id": f["chunk_id"], "document": f["chunk_id"].split(".pdf_")[0] + ".pdf"}
        for f in fragmentos
    ]

    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta basada en el contexto")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: fuentes)
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5,
        rag_evidence_min_score=0.30,
        rag_evidence_high_score=0.65,
    ))

    resultado = rag_pipeline.armar_respuesta("¿Qué significa HTM-0101?", "V2.0", "user", [])

    assert resultado["evidence_status"] == "high"
    assert resultado["sources"] == fuentes

def test_aviso_seguridad_se_devuelve_aunque_falte_version():
    resultado = rag_pipeline.armar_respuesta(
        "¿Qué significa HTM-0101?", "", "user", []
    )

    assert resultado["needs_clarification"] is True
    assert resultado["safety_alerts"][0]["code"] == "engine_overheating"


def test_aviso_seguridad_se_devuelve_si_no_hay_evidencia(monkeypatch):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: [{"score": 0.2}])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: (_ for _ in ()).throw(AssertionError()))

    resultado = rag_pipeline.armar_respuesta("¿Qué significa HTM-0101?", "V2.0", "user", [])

    assert resultado["evidence_status"] == "insufficient"
    assert resultado["safety_alerts"][0]["code"] == "engine_overheating"


def test_aviso_critico_se_conserva_si_falla_groq(monkeypatch):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: [{"score": 0.8}])
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: (_ for _ in ()).throw(RuntimeError("Groq no disponible")))
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))

    resultado = rag_pipeline.armar_respuesta(
        "Se ha encendido el testigo TES-05", "V2.0", "user", []
    )

    assert resultado["evidence_status"] == "insufficient"
    assert resultado["sources"] == []
    assert resultado["safety_alerts"][0]["code"] == "high_voltage"
    assert "No se ha podido generar" in resultado["message"]["content"]


def test_aviso_seguridad_se_adjunta_a_respuesta_generada(monkeypatch):
    fragmentos = [{"chunk_id": "DTC-001_1", "score": 0.75}]
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta documentada")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
    ))

    resultado = rag_pipeline.armar_respuesta(
        "El motor presenta sobrecalentamiento", "V2.0", "user", []
    )

    assert resultado["message"]["content"] == "Respuesta documentada"
    assert resultado["safety_alerts"][0]["code"] == "engine_overheating"


def test_verificacion_de_afirmaciones_se_incluye_en_la_respuesta(monkeypatch):
    fragmentos = [{"chunk_id": "DTC-001_1", "score": 0.75}]
    verificacion = {
        "status": "reviewed",
        "claims_total": 1,
        "claims_supported": 1,
        "claims": [{"claim": "Dato documentado", "status": "supported", "source_ids": ["DTC-001_1"], "evidence_excerpt": "Dato documentado"}],
    }
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta basada en el manual")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(rag_pipeline, "verificar_afirmaciones", lambda *_: verificacion)
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
        rag_claim_verification_enabled=True,
    ))

    resultado = rag_pipeline.armar_respuesta("Pregunta", "V1.0", "mechanic", [])

    assert resultado["claim_verification"] == verificacion


def test_verificacion_limita_respuesta_a_afirmaciones_respaldadas(monkeypatch):
    chunk_id = "HTM240-CAT-001_Catalogo_componentes.pdf_2"
    fragmentos = [{
        "chunk_id": chunk_id,
        "texto": "CMP-02: Caudal nominal 8-14 l/min, 12V, 3-6A",
        "seccion": "CMP-02",
        "pagina": 1,
        "score": 0.75,
    }]
    verificacion = {
        "status": "needs_review",
        "claims_total": 2,
        "claims_supported": 1,
        "claims": [
            {
                "claim": "CMP-02 tiene un caudal nominal de 8-14 l/min.",
                "status": "supported",
                "source_ids": [chunk_id],
                "evidence_excerpt": "Caudal nominal 8-14 l/min",
            },
            {
                "claim": "CMP-02 consume siempre 20 A.",
                "status": "not_found",
                "source_ids": [],
                "evidence_excerpt": None,
            },
        ],
    }
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda _prompt: "CMP-02 tiene un caudal de 8-14 l/min y siempre consume 20 A.",
    )
    monkeypatch.setattr(rag_pipeline, "verificar_afirmaciones", lambda *_: verificacion)

    def construir_fuentes(fragmentos_recibidos, _version, referencias):
        return [{
            "id": fragmento["chunk_id"],
            "document": "HTM240-CAT-001_Catalogo_componentes.pdf",
            "citation_status": "cited" if indice in referencias else "retrieved",
        } for indice, fragmento in enumerate(fragmentos_recibidos, start=1)]

    monkeypatch.setattr(rag_pipeline, "construir_fuentes", construir_fuentes)
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5,
        rag_evidence_min_score=0.3,
        rag_evidence_high_score=0.5,
        rag_claim_verification_enabled=True,
        rag_evidence_sufficiency_enabled=False,
    ))

    resultado = rag_pipeline.armar_respuesta("¿Qué caudal tiene CMP-02?", "V2.0", "mechanic", [])

    assert "caudal nominal de 8-14 l/min" in resultado["message"]["content"]
    assert "siempre consume 20 A" not in resultado["message"]["content"]
    assert resultado["claim_verification"]["answer_restricted"] is True
    assert resultado["evidence_status"] == "medium"
    assert resultado["sources"][0]["citation_status"] == "verified"
    assert "[F1]" in resultado["message"]["content"]


def test_verificacion_sin_afirmaciones_respaldadas_bloquea_respuesta_generada(monkeypatch):
    chunk_id = "HTM240-CAT-001_Catalogo_componentes.pdf_2"
    fragmentos = [{
        "chunk_id": chunk_id,
        "texto": "CMP-02: caudal 8-14 l/min",
        "seccion": "CMP-02",
        "pagina": 1,
        "score": 0.75,
    }]
    verificacion = {
        "status": "needs_review",
        "claims_total": 1,
        "claims_supported": 0,
        "claims": [{
            "claim": "CMP-02 entrega 8 bar.",
            "status": "not_found",
            "source_ids": [],
            "evidence_excerpt": None,
        }],
    }
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "CMP-02 entrega 8 bar.")
    monkeypatch.setattr(rag_pipeline, "verificar_afirmaciones", lambda *_: verificacion)
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda fs, _version, _refs: [{
        "id": fs[0]["chunk_id"],
        "document": "HTM240-CAT-001_Catalogo_componentes.pdf",
        "citation_status": "retrieved",
    }])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5,
        rag_evidence_min_score=0.3,
        rag_evidence_high_score=0.5,
        rag_claim_verification_enabled=True,
        rag_evidence_sufficiency_enabled=False,
    ))

    resultado = rag_pipeline.armar_respuesta("¿Qué presión tiene CMP-02?", "V2.0", "mechanic", [])

    assert "no se muestra la respuesta generada" in resultado["message"]["content"]
    assert "8 bar" not in resultado["message"]["content"]
    assert resultado["evidence_status"] == "insufficient"
    assert resultado["claim_verification"]["answer_restricted"] is True
    assert resultado["sources"][0]["citation_status"] == "retrieved"


def test_fallo_del_verificador_no_interrumpe_la_respuesta(monkeypatch):
    fragmentos = [{"chunk_id": "DTC-001_1", "score": 0.75}]
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta basada en el manual")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(
        rag_pipeline,
        "verificar_afirmaciones",
        lambda *_: (_ for _ in ()).throw(RuntimeError("verificador no disponible")),
    )
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
        rag_claim_verification_enabled=True,
    ))

    resultado = rag_pipeline.armar_respuesta("Pregunta", "V1.0", "mechanic", [])

    assert resultado["message"]["content"] == "Respuesta basada en el manual"
    assert resultado["claim_verification"]["status"] == "unavailable"


def test_pregunta_ambigua_pide_aclaracion_tecnica_antes_de_llamar_al_llm(monkeypatch):
    monkeypatch.setattr(
        rag_pipeline,
        "reformular_con_historial",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe reformular una pregunta ambigua")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "buscar_fragmentos",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe recuperar antes de aclarar")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe llamar a Groq")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(rag_ambiguity_detection_enabled=True),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Cómo compruebo la bomba auxiliar?", "V2.0", "mechanic", []
    )

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "technical"
    assert "CMP-02" in resultado["message"]["content"]
    assert "CMP-03" in resultado["message"]["content"]
    assert resultado["sources"] == []
    assert resultado["documents_consulted"] == 0


def test_seleccion_de_version_evita_duplicar_aclaracion_de_htm_0142(monkeypatch):
    fragmentos = [{"chunk_id": "HTM240-DTC-001_Catalogo_DTC.pdf_1", "score": 0.8}]
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: "Respuesta para V2.0")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(
            rag_ambiguity_detection_enabled=True,
            rag_top_k=5,
            rag_evidence_min_score=0.3,
            rag_evidence_high_score=0.5,
            rag_claim_verification_enabled=False,
        ),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué significa el código HTM-0142?", "V2.0", "mechanic", []
    )

    assert resultado["needs_clarification"] is False
    assert resultado["message"]["content"] == "Respuesta para V2.0"


def test_respuesta_a_aclaracion_tecnica_usa_el_historial_sin_repreguntar(monkeypatch):
    fragmentos = [{"chunk_id": "HTM240-PRC-003_1", "score": 0.75}]
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿Te refieres a la bomba auxiliar A (CMP-02) o B (CMP-03)?",
            "clarification_kind": "technical",
        },
    ]
    consultas_traducidas = []

    monkeypatch.setattr(
        rag_pipeline,
        "reformular_con_historial",
        lambda *_: (_ for _ in ()).throw(AssertionError(
            "La respuesta a una aclaración usa el contexto de forma determinista"
        )),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "traducir_consulta",
        lambda mensaje: consultas_traducidas.append(mensaje) or mensaje,
    )
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    mensajes_para_prompt = []
    monkeypatch.setattr(
        rag_pipeline,
        "construir_prompt",
        lambda mensaje, *_: mensajes_para_prompt.append(mensaje) or "prompt de prueba",
    )
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Comprueba CMP-02 según PRC-003.")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(
            rag_ambiguity_detection_enabled=True,
            rag_top_k=5,
            rag_evidence_min_score=0.3,
            rag_evidence_high_score=0.5,
            rag_claim_verification_enabled=False,
        ),
    )

    resultado = rag_pipeline.armar_respuesta("La bomba A", "V2.0", "mechanic", historial)

    assert resultado["needs_clarification"] is False
    assert resultado["message"]["content"] == "Comprueba CMP-02 según PRC-003."
    assert len(consultas_traducidas) == 1
    assert "¿Cómo compruebo la bomba auxiliar?" in consultas_traducidas[0]
    assert "bomba auxiliar A (CMP-02)" in consultas_traducidas[0]
    assert "CIR-02" in consultas_traducidas[0]
    assert "CMP-03" not in consultas_traducidas[0]
    # La misma pregunta contextualizada debe llegar al LLM, no solo «La bomba A».
    assert len(mensajes_para_prompt) == 1
    assert "¿Cómo compruebo la bomba auxiliar?" in mensajes_para_prompt[0]
    assert "bomba auxiliar A (CMP-02)" in mensajes_para_prompt[0]
    assert "CMP-03" not in mensajes_para_prompt[0]


def test_respuesta_vaga_a_aclaracion_tecnica_no_llama_al_rag(monkeypatch):
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿A cuál te refieres: bomba A (CMP-02) o bomba B (CMP-03)?",
            "clarification_kind": "technical",
        },
    ]
    monkeypatch.setattr(
        rag_pipeline,
        "buscar_fragmentos",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe recuperar con la aclaración pendiente")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe llamar al LLM")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(rag_ambiguity_detection_enabled=True),
    )

    resultado = rag_pipeline.armar_respuesta("No sé", "V2.0", "mechanic", historial)

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "technical"
    assert "bomba A (CMP-02) o bomba B (CMP-03)" in resultado["message"]["content"]


def test_version_mencionada_distinta_del_selector_pide_confirmacion_antes_del_rag(monkeypatch):
    monkeypatch.setattr(
        rag_pipeline,
        "reformular_con_historial",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe reformular una versión contradictoria")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "buscar_fragmentos",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe recuperar con una versión contradictoria")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe llamar a Groq")),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué significa HTM-0142 en V1.0?", "V2.0", "mechanic", []
    )

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "version_mismatch"
    assert "V2.0" in resultado["message"]["content"]
    assert "V1.0" in resultado["message"]["content"]
    assert resultado["sources"] == []
    assert resultado["documents_consulted"] == 0


def test_pregunta_que_coincide_con_la_version_seleccionada_continua_al_rag(monkeypatch):
    fragmentos = [{"chunk_id": "HTM240-DTC-001_Catalogo_DTC.pdf_1", "score": 0.8}]
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt de prueba")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: "Respuesta para V2.0")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(
            rag_top_k=5,
            rag_evidence_min_score=0.3,
            rag_evidence_high_score=0.5,
            rag_claim_verification_enabled=False,
            rag_ambiguity_detection_enabled=False,
        ),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué significa HTM-0142 en V2.0?", "V2.0", "mechanic", []
    )

    assert resultado["needs_clarification"] is False
    assert resultado["message"]["content"] == "Respuesta para V2.0"


def test_pregunta_comparativa_se_detiene_y_no_se_responde_con_una_sola_version(monkeypatch):
    monkeypatch.setattr(
        rag_pipeline,
        "buscar_fragmentos",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe consultar una sola versión")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe llamar a Groq")),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué diferencias hay entre V1.0 y V2.0 para HTM-0142?", "V2.0", "mechanic", []
    )

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "version_comparison"
    assert "una sola versión por turno" in resultado["message"]["content"]
    assert resultado["sources"] == []


def test_la_alerta_de_seguridad_se_conserva_si_hay_conflicto_de_version(monkeypatch):
    resultado = rag_pipeline.armar_respuesta(
        "Se ha encendido el testigo TES-05 en V1.0. ¿Qué debo hacer?", "V2.0", "user", []
    )

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "version_mismatch"
    assert any(alerta["code"] == "high_voltage" for alerta in resultado["safety_alerts"])


def _preparar_pipeline_r07(monkeypatch, fragmentos, *, suficiencia=True):
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(
            rag_top_k=5,
            rag_evidence_min_score=0.3,
            rag_evidence_high_score=0.5,
            rag_ambiguity_detection_enabled=False,
            rag_claim_verification_enabled=False,
            rag_evidence_sufficiency_enabled=suficiencia,
        ),
    )


def test_r07_bloquea_generacion_si_los_fragmentos_son_relacionados_pero_no_contienen_el_dato(monkeypatch):
    fragmentos = [
        {
            "chunk_id": "HTM240-PRC-004_2",
            "score": 0.74,
            "texto": "Compruebe el estado del fusible y mida la corriente del ventilador.",
        }
    ]
    _preparar_pipeline_r07(monkeypatch, fragmentos)
    monkeypatch.setattr(
        rag_pipeline,
        "evaluar_suficiencia_evidencia",
        lambda *_: {
            "status": "insufficient",
            "requested_items": [{
                "item": "Amperaje nominal del fusible",
                "status": "not_found",
                "source_ids": [],
                "evidence_excerpt": None,
            }],
            "missing_information": ["Amperaje nominal del fusible"],
        },
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("R07 debe bloquear la generación")),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué amperaje tiene el fusible?", "V2.0", "mechanic", []
    )

    assert resultado["evidence_status"] == "insufficient"
    assert resultado["sources"] == []
    assert resultado["evidence_sufficiency"]["status"] == "insufficient"
    assert "Amperaje nominal del fusible" in resultado["message"]["content"]


def test_r07_en_consulta_parcial_solo_entrega_al_generador_fragmentos_validados(monkeypatch):
    fragmentos = [
        {
            "chunk_id": "HTM240-CAT-001_1",
            "score": 0.82,
            "texto": "La bomba CMP-02 tiene una corriente nominal de 3-6 A.",
        },
        {
            "chunk_id": "HTM240-PRC-004_2",
            "score": 0.78,
            "texto": "Compruebe el estado del fusible y mida la corriente del ventilador.",
        },
    ]
    _preparar_pipeline_r07(monkeypatch, fragmentos)
    monkeypatch.setattr(
        rag_pipeline,
        "evaluar_suficiencia_evidencia",
        lambda *_: {
            "status": "partial",
            "requested_items": [
                {
                    "item": "Corriente nominal de CMP-02",
                    "status": "supported",
                    "source_ids": ["HTM240-CAT-001_1"],
                    "evidence_excerpt": "La bomba CMP-02 tiene una corriente nominal de 3-6 A.",
                },
                {
                    "item": "Amperaje nominal del fusible",
                    "status": "not_found",
                    "source_ids": [],
                    "evidence_excerpt": None,
                },
            ],
            "missing_information": ["Amperaje nominal del fusible"],
        },
    )
    prompt_args = {}

    def capturar_prompt(_mensaje, fragmentos_prompt, _perfil, _historial, _version, instruccion):
        prompt_args["ids"] = [fragmento["chunk_id"] for fragmento in fragmentos_prompt]
        prompt_args["instruccion"] = instruccion
        return "prompt parcial"

    monkeypatch.setattr(rag_pipeline, "construir_prompt", capturar_prompt)
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda _prompt: "### RESUMEN\nLa corriente es 3-6 A. No hay evidencia suficiente en la documentación para indicar el amperaje del fusible.",
    )
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])

    resultado = rag_pipeline.armar_respuesta(
        "Indica la corriente nominal de CMP-02 y el amperaje del fusible.",
        "V2.0",
        "mechanic",
        [],
    )

    assert prompt_args["ids"] == ["HTM240-CAT-001_1"]
    assert "Corriente nominal de CMP-02" in prompt_args["instruccion"]
    assert "Amperaje nominal del fusible" in prompt_args["instruccion"]
    assert resultado["evidence_sufficiency"]["status"] == "partial"
    assert resultado["evidence_status"] == "medium"


def test_r07_falla_cerrado_si_no_se_puede_evaluar_la_suficiencia(monkeypatch):
    fragmentos = [{"chunk_id": "HTM240-CAT-001_1", "score": 0.8, "texto": "Dato relacionado."}]
    _preparar_pipeline_r07(monkeypatch, fragmentos)
    monkeypatch.setattr(
        rag_pipeline,
        "evaluar_suficiencia_evidencia",
        lambda *_: (_ for _ in ()).throw(RuntimeError("evaluador caído")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe generar si R07 no está disponible")),
    )

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué valor tiene el componente?", "V2.0", "mechanic", []
    )

    assert resultado["evidence_status"] == "insufficient"
    assert resultado["evidence_sufficiency"]["status"] == "unavailable"
    assert "no he podido comprobar" in resultado["message"]["content"].lower()


def test_r07_puede_deshabilitarse_para_comparar_con_el_flujo_anterior(monkeypatch):
    fragmentos = [{"chunk_id": "HTM240-CAT-001_1", "score": 0.8, "texto": "Dato relacionado."}]
    _preparar_pipeline_r07(monkeypatch, fragmentos, suficiencia=False)
    monkeypatch.setattr(
        rag_pipeline,
        "evaluar_suficiencia_evidencia",
        lambda *_: (_ for _ in ()).throw(AssertionError("R07 está deshabilitado")),
    )
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt antiguo")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: "Respuesta anterior")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué valor tiene el componente?", "V2.0", "mechanic", []
    )

    assert resultado["message"]["content"] == "Respuesta anterior"
    assert resultado["evidence_sufficiency"]["status"] == "not_run"


def test_r07_con_cobertura_completa_entrega_solo_los_fragmentos_con_cita_validada(monkeypatch):
    fragmentos = [
        {"chunk_id": "HTM240-CAT-001_1", "score": 0.81, "texto": "CMP-02 tiene una corriente nominal de 3-6 A."},
        {"chunk_id": "HTM240-PRC-004_2", "score": 0.77, "texto": "Compruebe el estado del fusible correspondiente."},
    ]
    _preparar_pipeline_r07(monkeypatch, fragmentos)
    monkeypatch.setattr(
        rag_pipeline,
        "evaluar_suficiencia_evidencia",
        lambda *_: {
            "status": "sufficient",
            "requested_items": [{
                "item": "Corriente nominal de CMP-02",
                "status": "supported",
                "source_ids": ["HTM240-CAT-001_1"],
                "evidence_excerpt": "CMP-02 tiene una corriente nominal de 3-6 A.",
            }],
            "missing_information": [],
        },
    )
    recibidos = {}
    monkeypatch.setattr(
        rag_pipeline,
        "construir_prompt",
        lambda _mensaje, contexto, *_: recibidos.update(ids=[f["chunk_id"] for f in contexto]) or "prompt",
    )
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda *_: "Respuesta documentada")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])

    resultado = rag_pipeline.armar_respuesta(
        "¿Qué corriente nominal tiene CMP-02?", "V2.0", "mechanic", []
    )

    assert recibidos["ids"] == ["HTM240-CAT-001_1"]
    assert resultado["evidence_sufficiency"]["status"] == "sufficient"
    assert resultado["message"]["content"] == "Respuesta documentada"


def test_pregunta_generica_como_reviso_la_bomba_pide_aclaracion_entre_tres_bombas(monkeypatch):
    monkeypatch.setattr(
        rag_pipeline,
        "reformular_con_historial",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe reformular una pregunta ambigua")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "buscar_fragmentos",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe recuperar antes de aclarar")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe llamar a Groq")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(rag_ambiguity_detection_enabled=True),
    )

    resultado = rag_pipeline.armar_respuesta("¿Cómo reviso la bomba?", "V2.0", "mechanic", [])

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "technical"
    assert all(codigo in resultado["message"]["content"] for codigo in ("CMP-01", "CMP-02", "CMP-03"))
    assert resultado["sources"] == []
    assert resultado["documents_consulted"] == 0


def test_pregunta_por_caudal_de_bomba_sin_identificar_pide_aclaracion(monkeypatch):
    monkeypatch.setattr(
        rag_pipeline,
        "reformular_con_historial",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe reformular una consulta ambigua")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "buscar_fragmentos",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe recuperar antes de aclarar")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "generar_respuesta",
        lambda *_: (_ for _ in ()).throw(AssertionError("No debe llamar a Groq")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "settings",
        SimpleNamespace(rag_ambiguity_detection_enabled=True),
    )

    resultado = rag_pipeline.armar_respuesta("¿Qué caudal nominal tiene la bomba?", "V2.0", "mechanic", [])

    assert resultado["needs_clarification"] is True
    assert resultado["clarification_kind"] == "technical"
    assert all(codigo in resultado["message"]["content"] for codigo in ("CMP-01", "CMP-02", "CMP-03"))
    assert resultado["sources"] == []
    assert resultado["documents_consulted"] == 0


def test_pregunta_nueva_tras_aclaracion_tecnica_no_repite_la_aclaracion(monkeypatch):
    historial = [
        {"role": "user", "content": "¿Cómo reviso la bomba?"},
        {
            "role": "assistant",
            "content": "¿A cuál bomba te refieres: CMP-01, CMP-02 o CMP-03?",
            "clarification_kind": "technical",
        },
    ]
    fragmentos = [{"chunk_id": "HTM240-DTC-001_1", "score": 0.8}]
    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: fragmentos)
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda *_: "prompt")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "HTM-0142 indica...")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
        rag_ambiguity_detection_enabled=True,
    ))

    resultado = rag_pipeline.armar_respuesta("¿Qué significa el código HTM-0142?", "V1.0", "mechanic", historial)

    assert resultado["needs_clarification"] is False
    assert resultado["message"]["content"] == "HTM-0142 indica..."


def test_busqueda_tras_aclaracion_no_incluye_instrucciones_del_prompt(monkeypatch):
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿A cuál te refieres: bomba A (CMP-02) o bomba B (CMP-03)?",
            "clarification_kind": "technical",
        },
    ]
    buscadas: list[str] = []
    prompts: list[str] = []
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(
        rag_pipeline, "buscar_fragmentos",
        lambda consulta, *_: buscadas.append(consulta) or [{"chunk_id": "PRC-003_8", "score": 0.8}],
    )
    monkeypatch.setattr(rag_pipeline, "construir_prompt", lambda mensaje, *_: prompts.append(mensaje) or "prompt")
    monkeypatch.setattr(rag_pipeline, "generar_respuesta", lambda _prompt: "Respuesta")
    monkeypatch.setattr(rag_pipeline, "construir_fuentes", lambda *_: [])
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
        rag_ambiguity_detection_enabled=True,
    ))

    rag_pipeline.armar_respuesta("La bomba A", "V2.0", "mechanic", historial)

    assert "CMP-02" in buscadas[0]
    assert "no vuelvas a solicitarla" not in buscadas[0]
    assert "no vuelvas a solicitarla" in prompts[0]


def test_r07_sin_servicio_de_ia_devuelve_el_error_del_servicio(monkeypatch):
    import pytest
    from services.errores_llm import LLMServiceError

    def sin_servicio(*_args, **_kwargs):
        raise LLMServiceError("rate_limit", "El servicio de IA está saturado. Inténtalo más tarde.", http_status=429)

    monkeypatch.setattr(rag_pipeline, "reformular_con_historial", lambda mensaje, _historial: mensaje)
    monkeypatch.setattr(rag_pipeline, "traducir_consulta", lambda mensaje: mensaje)
    monkeypatch.setattr(rag_pipeline, "buscar_fragmentos", lambda *_: [{"chunk_id": "A_1", "score": 0.8}])
    monkeypatch.setattr(rag_pipeline, "anadir_notas_de_alcance", lambda _p, fragmentos, _v: fragmentos)
    monkeypatch.setattr(rag_pipeline, "evaluar_suficiencia_evidencia", sin_servicio)
    monkeypatch.setattr(rag_pipeline, "settings", SimpleNamespace(
        rag_top_k=5, rag_evidence_min_score=0.3, rag_evidence_high_score=0.5,
        rag_evidence_sufficiency_enabled=True,
    ))

    with pytest.raises(LLMServiceError):
        rag_pipeline.armar_respuesta("¿Qué corriente tiene CMP-02?", "V1.0", "mechanic", [])

    # Con un aviso de seguridad se responde igualmente para no perder el aviso.
    resultado = rag_pipeline.armar_respuesta("Se ha encendido el testigo TES-05", "V1.0", "user", [])
    assert resultado["safety_alerts"]
    assert "No se ha podido generar" in resultado["message"]["content"]
