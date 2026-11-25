"""Pruebas unitarias de la revisión de afirmaciones sin llamar a Groq."""

import json

from services.verificacion import verificar_afirmaciones


FRAGMENTOS = [
    {
        "chunk_id": "HTM240-DTC-001_Catalogo_DTC.pdf_1",
        "texto": "HTM-0101 indica sobretemperatura del motor cuando el refrigerante supera 118 °C durante más de 30 s.",
        "seccion": "HTM-0101",
        "pagina": 1,
    },
    {
        "chunk_id": "HTM240-DIA-001_Manual_diagnostico.pdf_2",
        "texto": "Ante una temperatura elevada, detenga el motor y no abra el depósito de refrigerante en caliente.",
        "seccion": "4.1 Sobrecalentamiento",
        "pagina": 4,
    },
]


def _respuesta_verificador(claims):
    return json.dumps({"claims": claims}, ensure_ascii=False)


def test_acepta_afirmacion_con_cita_literal_en_fuente():
    resultado = verificar_afirmaciones(
        "El código HTM-0101 indica sobretemperatura del motor.",
        FRAGMENTOS,
        generador=lambda _prompt: _respuesta_verificador([
            {
                "claim": "HTM-0101 indica sobretemperatura del motor.",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "HTM-0101 indica sobretemperatura del motor",
            }
        ]),
    )

    assert resultado["status"] == "reviewed"
    assert resultado["claims_total"] == 1
    assert resultado["claims_supported"] == 1
    assert resultado["claims"][0]["status"] == "supported"
    assert resultado["claims"][0]["source_ids"] == [FRAGMENTOS[0]["chunk_id"]]


def test_no_acepta_como_respaldada_una_cita_que_no_existe():
    resultado = verificar_afirmaciones(
        "El componente trabaja a 300 °C.",
        FRAGMENTOS,
        generador=lambda _prompt: _respuesta_verificador([
            {
                "claim": "El componente trabaja a 300 °C.",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "El componente trabaja a 300 °C",
            }
        ]),
    )

    assert resultado["status"] == "needs_review"
    assert resultado["claims_supported"] == 0
    assert resultado["claims"][0]["status"] == "unverified"
    assert resultado["claims"][0]["source_ids"] == []


def test_ignora_referencias_inventadas_del_verificador():
    resultado = verificar_afirmaciones(
        "El motor se sobrecalienta.",
        FRAGMENTOS,
        generador=lambda _prompt: _respuesta_verificador([
            {
                "claim": "El motor se sobrecalienta.",
                "status": "supported",
                "source_refs": ["F99"],
                "evidence_quote": "HTM-0101 indica sobretemperatura del motor",
            }
        ]),
    )

    assert resultado["claims"][0]["status"] == "unverified"
    assert resultado["claims"][0]["source_ids"] == []


def test_informa_cuando_no_hay_respaldo_en_los_fragmentos():
    resultado = verificar_afirmaciones(
        "La bomba entrega 8 bar.",
        FRAGMENTOS,
        generador=lambda _prompt: _respuesta_verificador([
            {
                "claim": "La bomba entrega 8 bar.",
                "status": "not_found",
                "source_refs": [],
                "evidence_quote": "",
            }
        ]),
    )

    assert resultado["status"] == "needs_review"
    assert resultado["claims"][0]["status"] == "not_found"


def test_marca_como_conflictiva_una_afirmacion_con_extracto_contradictorio():
    resultado = verificar_afirmaciones(
        "Se puede abrir el depósito con el motor caliente.",
        FRAGMENTOS,
        generador=lambda _prompt: _respuesta_verificador([
            {
                "claim": "Se puede abrir el depósito con el motor caliente.",
                "status": "conflicting",
                "source_refs": ["F2"],
                "evidence_quote": "no abra el depósito de refrigerante en caliente",
            }
        ]),
    )

    assert resultado["status"] == "needs_review"
    assert resultado["claims"][0]["status"] == "conflicting"
    assert resultado["claims"][0]["source_ids"] == [FRAGMENTOS[1]["chunk_id"]]


def test_respuesta_sin_afirmaciones_comprobables():
    resultado = verificar_afirmaciones(
        "De acuerdo. ¿Quieres revisar otra cosa?",
        FRAGMENTOS,
        generador=lambda _prompt: '{"claims": []}',
    )

    assert resultado["status"] == "no_claims"
    assert resultado["claims_total"] == 0
    assert resultado["claims"] == []


def test_el_prompt_incluye_fragmentos_con_identificadores_y_no_usa_fuente_del_modelo():
    prompts = []
    respuesta = (
        "### RESUMEN\nHTM-0101 indica sobretemperatura.\n\n"
        "### FUENTE\n- [F1] una cita del primer modelo"
    )

    verificar_afirmaciones(
        respuesta,
        FRAGMENTOS,
        generador=lambda prompt: prompts.append(prompt) or '{"claims": []}',
    )

    assert "[F1] Documento:" in prompts[0]
    assert "HTM-0101 indica sobretemperatura." in prompts[0]
    assert "una cita del primer modelo" not in prompts[0]


def test_acepta_cita_literal_con_referencia_mal_numerada():
    fragmentos = [
        {"chunk_id": "A_1", "texto": "Texto sin relación con la bomba."},
        {"chunk_id": "B_2", "texto": "3. Forzar la activación de la bomba CMP-02 al 100% desde el menú de diagnóstico."},
    ]
    resultado = verificar_afirmaciones(
        "Activa la bomba CMP-02 al 100 %.",
        fragmentos,
        generador=lambda _prompt: _respuesta_verificador([
            {
                "claim": "Activa la bomba CMP-02 al 100 %.",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "Forzar la activación de la bomba CMP-02 al 100%",
            }
        ]),
    )

    assert resultado["claims"][0]["status"] == "supported"
    assert resultado["claims"][0]["source_ids"] == ["B_2"]
