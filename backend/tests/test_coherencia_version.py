import pytest

from services.coherencia_version import (
    detectar_incoherencia_version,
    extraer_versiones_mencionadas,
)


@pytest.mark.parametrize(
    "texto,esperadas",
    [
        ("¿Qué significa HTM-0142 en V1.0?", ["V1.0"]),
        ("Consulta la versión 1.1 del motor", ["V1.1"]),
        ("¿Qué cambia en v 2,0?", ["V2.0"]),
        ("Compara V1.0 y V2.0", ["V1.0", "V2.0"]),
        ("CMP-09 trabaja a 12.0 V", []),
    ],
)
def test_extrae_solo_versiones_explicitas(texto, esperadas):
    assert extraer_versiones_mencionadas(texto) == esperadas


def test_no_detecta_conflicto_si_la_pregunta_coincide_con_el_selector():
    assert detectar_incoherencia_version(
        "¿Qué significa HTM-0142 en V2.0?", "V2.0"
    ) is None


def test_detecta_conflicto_si_la_pregunta_menciona_otra_version():
    resultado = detectar_incoherencia_version(
        "¿Qué significa HTM-0142 en V1.0?", "V2.0"
    )
    assert resultado is not None
    assert resultado["kind"] == "version_mismatch"
    assert resultado["selected_version"] == "V2.0"
    assert resultado["mentioned_version"] == "V1.0"
    assert "cambia el selector a V1.0" in resultado["message"]


def test_detecta_comparacion_de_varias_versiones_sin_tratarla_como_un_conflicto_simple():
    resultado = detectar_incoherencia_version(
        "¿Qué diferencias hay entre V1.0 y V2.0 para HTM-0142?", "V2.0"
    )
    assert resultado is not None
    assert resultado["kind"] == "version_comparison"
    assert resultado["versions"] == ["V1.0", "V2.0"]
    assert "una sola versión por turno" in resultado["message"]


def test_avisa_si_la_pregunta_menciona_una_version_no_documentada():
    resultado = detectar_incoherencia_version(
        "Consulta el procedimiento para V3.0", "V2.0"
    )
    assert resultado is not None
    assert resultado["kind"] == "version_mismatch"
    assert "V3.0" in resultado["message"]
    assert "no está entre las versiones documentadas" in resultado["message"]
