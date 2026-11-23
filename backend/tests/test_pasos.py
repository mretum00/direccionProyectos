"""Pruebas de los pasos seguidos por fases (services/pasos.py)."""

from datetime import datetime

from services.pasos import paso_transformacion

FECHA = datetime(2026, 11, 23, 13, 48, 52).astimezone()


def test_muestra_la_transformacion_de_la_pregunta_original_a_la_consulta_tecnica():
    pregunta = "Se enciende un testigo y falla TES-01"
    paso = paso_transformacion(
        "V1.0", "user", pregunta, pregunta,
        f"{pregunta} (Se enciende el testigo TES-01; revisar CMP‑01 y HTM-0142)",
        FECHA,
    )

    assert paso["kind"] == "query"
    assert paso["detail"] == (
        "Versión V1.0 · Perfil conductor · Consulta realizada el 23/11/2026 a las 13:48:52"
    )
    original, tecnica = paso["stages"]
    assert original == {"label": "Pregunta original", "text": pregunta}
    # Solo la parte generada, con el guion normalizado y los códigos nuevos (TES-01 ya estaba).
    assert tecnica["label"] == "Consulta técnica generada"
    assert tecnica["text"] == "Se enciende el testigo TES-01; revisar CMP-01 y HTM-0142"
    assert tecnica["terms"] == ["CMP-01", "HTM-0142"]


def test_incluye_la_reformulacion_con_el_historial_si_la_hay():
    paso = paso_transformacion("V2.0", "mechanic", "¿Y eso?", "¿Qué es CMP-02?", "¿Qué es CMP-02?")

    assert [etapa["label"] for etapa in paso["stages"]] == [
        "Pregunta original", "Reformulada con el historial", "Consulta técnica generada",
    ]
    assert paso["stages"][1]["text"] == "¿Qué es CMP-02?"


def test_si_el_glosario_no_aporta_nada_se_indica():
    for tecnica in ("Pregunta", "Pregunta (Pregunta)"):
        etapa = paso_transformacion("V1.0", "user", "Pregunta", "Pregunta", tecnica)["stages"][-1]
        assert etapa["text"] == "Pregunta"
        assert "no ha aportado" in etapa["note"]


def test_siempre_indica_cuando_se_hizo_la_consulta():
    paso = paso_transformacion("V1.0", "user", "Pregunta", "Pregunta", "Pregunta")
    assert "Consulta realizada el " in paso["detail"]
