"""Pruebas de respuestas deterministas y seguras de la API."""

from services.respuestas import (
    _extracto,
    pedir_aclaracion,
    respuesta_limitada_por_verificacion,
    respuesta_sin_evidencia,
    normalizar_intervalos_caudal,
)


def test_respuesta_sin_evidencia_no_inventa_fuentes_ni_datos():
    resultado = respuesta_sin_evidencia()

    assert resultado["evidence_status"] == "insufficient"
    assert resultado["sources"] == []
    assert resultado["documents_consulted"] == 0
    assert "No hay información suficiente" in resultado["message"]["content"]


def test_pedir_aclaracion_solo_solicita_la_version_del_motor():
    resultado = pedir_aclaracion("")

    assert resultado["needs_clarification"] is True
    assert "versión del motor" in resultado["message"]["content"]
    assert "tipo de usuario" not in resultado["message"]["content"]


def test_extracto_de_700_caracteres_conserva_el_fragmento_cmp02_completo():
    texto = (
        "CMP-02 — Bomba electrica auxiliar A (circuito bateria) • Función: Impulsar refrigerante "
        "dedicado al pack de bateria de alta tension • Circuito / ubicación funcional: Circuito "
        "termico de la bateria de alta tension • Valores nominales: Caudal 8-14 l/min, 12V, 3-6A "
        "• Posibles modos de fallo: Bobinado deteriorado, Rotor bloqueado, Conector oxidado "
        "• Síntomas asociados: Temperatura bateria elevada, Ruido agudo intermitente, DTC de flujo "
        "bajo • Documentos relacionados: HTM240-MAN-001 (Manual general), HTM240-DIA-001 "
        "(Manual de diagnóstico), HTM240-DTC-001 (Catálogo DTC)"
    )

    extracto = _extracto(texto, 700)

    assert extracto == texto
    assert "Caudal 8-14 l/min, 12V, 3-6A" in extracto
    assert "DTC de flujo bajo" in extracto


def test_respuesta_limitada_conserva_solo_afirmaciones_con_cita_literal_valida():
    fragmentos = [
        {
            "chunk_id": "HTM240-CAT-001_Catalogo_componentes.pdf_2",
            "texto": "CMP-02: Caudal nominal 8-14 l/min, 12V, 3-6A",
            "seccion": "CMP-02",
            "pagina": 1,
        },
        {
            "chunk_id": "HTM240-DTC-001_Catalogo_DTC.pdf_4",
            "texto": "HTM-0202: fallo de comunicación de batería",
            "seccion": "HTM-0202",
            "pagina": 5,
        },
    ]
    verificacion = {
        "status": "needs_review",
        "claims_total": 2,
        "claims_supported": 1,
        "claims": [
            {
                "claim": "CMP-02 tiene un caudal nominal de 8-14 l/min.",
                "status": "supported",
                "source_ids": [fragmentos[0]["chunk_id"]],
                "evidence_excerpt": "Caudal nominal 8-14 l/min",
            },
            {
                "claim": "CMP-02 siempre provoca HTM-9999 cuando se bloquea.",
                "status": "not_found",
                "source_ids": [],
                "evidence_excerpt": None,
            },
        ],
    }

    texto, referencias = respuesta_limitada_por_verificacion(verificacion, fragmentos)

    assert "caudal nominal de 8-14 l/min" in texto
    assert "siempre provoca HTM-9999" not in texto
    assert "Se han omitido 1 afirmación" in texto
    assert "[F1]" in texto
    assert "[F2]" not in texto
    assert referencias == {1}


def test_respuesta_limitada_se_abstiene_si_no_hay_afirmaciones_respaldadas():
    verificacion = {
        "status": "needs_review",
        "claims_total": 1,
        "claims_supported": 0,
        "claims": [{
            "claim": "La bomba entrega 8 bar.",
            "status": "not_found",
            "source_ids": [],
            "evidence_excerpt": None,
        }],
    }

    texto, referencias = respuesta_limitada_por_verificacion(verificacion, [
        {"chunk_id": "HTM240-CAT-001_Catalogo_componentes.pdf_2", "texto": "CMP-02: caudal 8-14 l/min"}
    ])

    assert "no se muestra la respuesta generada" in texto
    assert "8 bar" not in texto
    assert referencias == set()

def test_normalizar_intervalo_caudal_sin_espacios():
    texto = "El caudal nominal es de 8a14l/min."

    resultado = normalizar_intervalos_caudal(texto)

    assert resultado == "El caudal nominal es de 8-14 l/min."


def test_normalizar_intervalo_caudal_con_preposicion():
    texto = "El caudal nominal está entre 8 a 14 l/min."

    resultado = normalizar_intervalos_caudal(texto)

    assert resultado == "El caudal nominal está entre 8-14 l/min."


def test_normalizar_intervalo_caudal_con_guion():
    texto = "El caudal nominal es de 8–14l/min."

    resultado = normalizar_intervalos_caudal(texto)

    assert resultado == "El caudal nominal es de 8-14 l/min."


def test_normalizar_intervalo_caudal_no_modifica_otros_datos():
    texto = "La corriente nominal es de 3-6 A a 12V."

    resultado = normalizar_intervalos_caudal(texto)

    assert resultado == texto
