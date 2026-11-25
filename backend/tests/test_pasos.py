"""Pruebas de los pasos observables del flujo RAG (sin exponer CoT del LLM)."""

from datetime import datetime, timezone

from services.pasos import paso_busqueda, paso_conclusion, paso_cobertura, paso_transformacion


def test_paso_transformacion_muestra_pregunta_y_consulta_tecnica():
    paso = paso_transformacion(
        "V2.0",
        "mechanic",
        "¿Qué ocurre con la bomba?",
        "¿Qué ocurre con la bomba CMP-02?",
        "¿Qué ocurre con la bomba CMP-02? (verificar circuito CIR-02)",
        datetime(2026, 11, 24, 10, 30, tzinfo=timezone.utc),
    )

    assert paso["kind"] == "query"
    assert [stage["label"] for stage in paso["stages"]] == [
        "Pregunta original",
        "Reformulada con el historial",
        "Consulta técnica para la búsqueda",
    ]
    assert "CIR-02" in paso["stages"][-1]["terms"]


def test_paso_busqueda_distingue_fragmentos_citados_de_no_citados():
    fragmentos = [
        {"chunk_id": "HTM240-CAT-001_catalogo.pdf_1", "score": 0.82, "pagina": 2, "seccion": "CMP-02"},
        {"chunk_id": "HTM240-PRC-001_proc.pdf_2", "score": 0.61, "pagina": 4},
    ]

    paso = paso_busqueda("V2.0", fragmentos, {"HTM240-CAT-001_catalogo.pdf_1"})

    assert paso["kind"] == "search"
    assert len(paso["fragments"]) == 2
    assert paso["fragments"][0]["used"] is True
    assert paso["fragments"][1]["used"] is False
    assert paso["fragments"][0]["source_type"] == "manual"


def test_paso_cobertura_resume_resultado_r07_sin_razonamiento_interno():
    suficiencia = {
        "status": "partial",
        "requested_items": [
            {"item": "caudal nominal de CMP-02", "status": "supported", "source_ids": ["HTM240-CAT-001_catalogo.pdf_1"]},
            {"item": "amperaje del fusible", "status": "not_found", "source_ids": []},
        ],
        "missing_information": ["amperaje del fusible"],
    }

    paso = paso_cobertura(suficiencia)

    assert paso["kind"] == "analysis"
    assert "Cobertura documental parcial" == paso["title"]
    assert len(paso["points"]) == 2
    assert "caudal nominal" in paso["points"][0]["text"]
    assert "no localizado" in paso["points"][1]["text"]
    assert "razonamiento" not in " ".join(point["text"] for point in paso["points"]).lower()


def test_paso_cobertura_no_se_crea_si_r07_no_se_ejecuto():
    assert paso_cobertura({"status": "not_run", "requested_items": []}) is None


def test_paso_conclusion_indica_bloqueo_por_evidencia_insuficiente():
    paso = paso_conclusion(
        "insufficient", 0.72, 0.30, 0.65,
        detalle_extra="R07 no encontró evidencia suficiente.",
    )

    assert paso["kind"] == "conclusion"
    assert paso["evidence"] == "insufficient"
    assert "R07" in paso["detail"]
