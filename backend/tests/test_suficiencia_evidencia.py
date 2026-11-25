"""Pruebas de la clasificación y validación local de cobertura documental (R07)."""

import json

from services.suficiencia_evidencia import (
    evaluar_suficiencia_evidencia,
    fragmentos_con_evidencia_validada,
)

FRAGMENTOS = [
    {
        "chunk_id": "HTM240-CAT-001_Catalogo_Componentes.pdf_1",
        "texto": "La bomba eléctrica auxiliar CMP-02 tiene una corriente nominal de 3-6 A.",
        "seccion": "CMP-02",
        "pagina": 12,
        "score": 0.82,
    },
    {
        "chunk_id": "HTM240-PRC-004_Procedimiento.pdf_2",
        "texto": "Compruebe el estado del fusible de alimentación y mida la corriente del ventilador.",
        "seccion": "Comprobaciones eléctricas",
        "pagina": 18,
        "score": 0.76,
    },
]


def _salida(items):
    return json.dumps({"items": items}, ensure_ascii=False)


def test_acepta_cobertura_completa_con_cita_literal_validada():
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué corriente nominal tiene CMP-02?",
        FRAGMENTOS,
        generador=lambda _prompt: _salida([
            {
                "item": "Corriente nominal de CMP-02",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "La bomba eléctrica auxiliar CMP-02 tiene una corriente nominal de 3-6 A.",
            }
        ]),
    )

    assert resultado["status"] == "sufficient"
    assert resultado["requested_items"][0]["status"] == "supported"
    assert resultado["requested_items"][0]["source_ids"] == [FRAGMENTOS[0]["chunk_id"]]
    assert resultado["missing_information"] == []
    assert fragmentos_con_evidencia_validada(FRAGMENTOS, resultado) == [FRAGMENTOS[0]]


def test_no_confunde_mencionar_un_fusible_con_documentar_su_amperaje():
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué amperaje nominal tiene el fusible?",
        FRAGMENTOS[1:],
        generador=lambda _prompt: _salida([
            {
                "item": "Amperaje nominal del fusible",
                "status": "not_found",
                "source_refs": [],
                "evidence_quote": "",
            }
        ]),
    )

    assert resultado["status"] == "insufficient"
    assert resultado["missing_information"] == ["Amperaje nominal del fusible"]
    assert fragmentos_con_evidencia_validada(FRAGMENTOS[1:], resultado) == []


def test_degrada_a_incierta_una_evidencia_positiva_con_cita_inventada():
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué corriente nominal tiene CMP-02?",
        FRAGMENTOS,
        generador=lambda _prompt: _salida([
            {
                "item": "Corriente nominal de CMP-02",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "La corriente nominal es de 15 A.",
            }
        ]),
    )

    assert resultado["status"] == "insufficient"
    assert resultado["requested_items"][0]["status"] == "uncertain"
    assert resultado["requested_items"][0]["source_ids"] == []
    assert fragmentos_con_evidencia_validada(FRAGMENTOS, resultado) == []


def test_detecta_cobertura_parcial_y_conserva_solo_fuentes_del_dato_respaldado():
    resultado = evaluar_suficiencia_evidencia(
        "Indica la corriente nominal de CMP-02 y el par de apriete de CMP-24.",
        FRAGMENTOS,
        generador=lambda _prompt: _salida([
            {
                "item": "Corriente nominal de CMP-02",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "La bomba eléctrica auxiliar CMP-02 tiene una corriente nominal de 3-6 A.",
            },
            {
                "item": "Par de apriete de CMP-24",
                "status": "not_found",
                "source_refs": [],
                "evidence_quote": "",
            },
        ]),
    )

    assert resultado["status"] == "partial"
    assert resultado["missing_information"] == ["Par de apriete de CMP-24"]
    assert fragmentos_con_evidencia_validada(FRAGMENTOS, resultado) == [FRAGMENTOS[0]]


def test_no_acepta_referencias_inventadas_a_fragmentos():
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué corriente nominal tiene CMP-02?",
        FRAGMENTOS,
        generador=lambda _prompt: _salida([
            {
                "item": "Corriente nominal de CMP-02",
                "status": "supported",
                "source_refs": ["F99"],
                "evidence_quote": "La bomba eléctrica auxiliar CMP-02 tiene una corriente nominal de 3-6 A.",
            }
        ]),
    )

    assert resultado["status"] == "insufficient"
    assert resultado["requested_items"][0]["status"] == "uncertain"


def test_rechaza_salida_json_sin_elementos_solicitados():
    import pytest

    with pytest.raises(ValueError, match="al menos un elemento"):
        evaluar_suficiencia_evidencia(
            "¿Qué corriente nominal tiene CMP-02?",
            FRAGMENTOS,
            generador=lambda _prompt: '{"items": []}',
        )


def test_prompt_separa_la_pregunta_del_contexto_documental():
    prompts = []
    evaluar_suficiencia_evidencia(
        "¿Qué corriente nominal tiene CMP-02?",
        FRAGMENTOS,
        generador=lambda prompt: prompts.append(prompt) or _salida([
            {
                "item": "Corriente nominal de CMP-02",
                "status": "not_found",
                "source_refs": [],
                "evidence_quote": "",
            }
        ]),
    )

    assert "¿Qué corriente nominal tiene CMP-02?" in prompts[0]
    assert "[F1] Documento:" in prompts[0]
    assert "3-6 A" in prompts[0]
    assert "La mera coincidencia de palabras o códigos no basta" in prompts[0]


def test_no_confunde_refrigerante_del_circuito_termico_con_gas_del_aire_acondicionado():
    fragmentos = [
        {
            "chunk_id": "manual_thermodrive_1",
            "texto": "El refrigerante ThermoGlyc HX-40 circula por los tres circuitos térmicos.",
            "seccion": "Circuitos térmicos",
            "pagina": 4,
        },
        {
            "chunk_id": "diccionario_alcance_1",
            "texto": "El aire acondicionado no enfría: Fuera del alcance de este corpus; ThermoDrive no gestiona el circuito de A/C del habitáculo.",
            "seccion": "Diccionario técnico",
            "pagina": 2,
        },
    ]
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué refrigerante debo utilizar para recargar el aire acondicionado del habitáculo?",
        fragmentos,
        generador=lambda _prompt: _salida([
            {
                "item": "Refrigerante a utilizar",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "El refrigerante ThermoGlyc HX-40 circula por los tres circuitos térmicos.",
            }
        ]),
    )

    assert resultado["status"] == "insufficient"
    assert resultado["requested_items"][0]["status"] == "not_found"
    assert resultado["requested_items"][0]["source_ids"] == []


def test_acepta_refrigerante_si_la_cita_identifica_el_mismo_sistema_y_el_valor():
    fragmentos = [{
        "chunk_id": "manual_ac_1",
        "texto": "El aire acondicionado del habitáculo utiliza refrigerante R-1234yf.",
        "seccion": "Aire acondicionado",
        "pagina": 8,
    }]
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué refrigerante utiliza el aire acondicionado del habitáculo?",
        fragmentos,
        generador=lambda _prompt: _salida([
            {
                "item": "Refrigerante utilizado",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "El aire acondicionado del habitáculo utiliza refrigerante R-1234yf.",
            }
        ]),
    )

    assert resultado["status"] == "sufficient"
    assert resultado["requested_items"][0]["status"] == "supported"


def test_acepta_presion_solo_si_la_cita_incluye_valor_y_unidad_del_mismo_sistema():
    fragmentos = [{
        "chunk_id": "manual_ac_2",
        "texto": "La presión de carga del aire acondicionado del habitáculo es 2.1 bar.",
        "seccion": "Aire acondicionado",
        "pagina": 9,
    }]
    resultado = evaluar_suficiencia_evidencia(
        "¿Qué presión debo utilizar en el aire acondicionado del habitáculo?",
        fragmentos,
        generador=lambda _prompt: _salida([
            {
                "item": "Presión de carga",
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": "La presión de carga del aire acondicionado del habitáculo es 2.1 bar.",
            }
        ]),
    )

    assert resultado["status"] == "sufficient"
    assert resultado["requested_items"][0]["status"] == "supported"
