"""Pruebas de respuestas deterministas y seguras de la API."""

from services.respuestas import pedir_aclaracion, respuesta_sin_evidencia


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
