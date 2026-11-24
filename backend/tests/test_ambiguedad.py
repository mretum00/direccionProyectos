import pytest

from services.ambiguedad import (
    detectar_aclaracion_tecnica,
    hay_aclaracion_tecnica_pendiente,
    consulta_autonoma_tras_aclaracion,
)


@pytest.mark.parametrize(
    "pregunta,codigo",
    [
        ("¿Cómo compruebo la bomba auxiliar?", "pump_variant"),
        ("¿Cómo verifico el sensor de temperatura?", "temperature_sensor"),
        ("La temperatura del sistema está fuera de rango. ¿Qué debería revisar?", "thermal_circuit"),
        ("Se ha encendido un testigo rojo. ¿Debo detenerme?", "red_indicator"),
        ("La calefacción no funciona. ¿Qué componente tengo que sustituir?", "heating_diagnosis"),
        ("¿Cada cuánto tengo que hacer el mantenimiento?", "maintenance_target"),
    ],
)
def test_detecta_ambiguedades_r06_concretas(pregunta, codigo):
    resultado = detectar_aclaracion_tecnica(pregunta)
    assert resultado is not None
    assert resultado["code"] == codigo


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Qué caudal nominal tiene la bomba?",
        "¿Cómo compruebo la bomba auxiliar A CMP-02?",
        "¿Cómo verifico el sensor de batería CMP-15?",
        "¿Cómo compruebo el circuito CIR-02?",
        "¿Qué significa el código HTM-0142?",
        "¿Qué amperaje tiene el fusible CMP-09?",
        "¿Cada cuánto se sustituye el filtro CMP-24?",
    ],
)
def test_no_pide_aclaracion_si_la_consulta_ya_es_suficientemente_concreta(pregunta):
    assert detectar_aclaracion_tecnica(pregunta) is None


def test_identifica_que_el_usuario_esta_respondiendo_a_una_aclaracion():
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿Te refieres a la bomba auxiliar A o B?",
            "clarification_kind": "technical",
        },
    ]
    assert hay_aclaracion_tecnica_pendiente(historial) is True


def test_no_identifica_una_aclaracion_pendiente_tras_una_respuesta_normal():
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar A?"},
        {"role": "assistant", "content": "Consulta los pasos de PRC-003."},
    ]
    assert hay_aclaracion_tecnica_pendiente(historial) is False



def test_combina_pregunta_original_y_respuesta_a_aclaracion():
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿Te refieres a la bomba auxiliar A o B?",
            "clarification_kind": "technical",
        },
    ]

    consulta = consulta_autonoma_tras_aclaracion("La bomba A", historial)

    assert "¿Cómo compruebo la bomba auxiliar?" in consulta
    assert "bomba auxiliar A (CMP-02)" in consulta
    assert "CIR-02" in consulta
    assert "CMP-03" not in consulta


def test_resuelve_la_bomba_a_con_codigo_y_circuito_explicitos():
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿A cuál te refieres: bomba A (CMP-02), circuito CIR-02, o bomba B (CMP-03), circuito CIR-03?",
            "clarification_kind": "technical",
        },
    ]
    consulta = consulta_autonoma_tras_aclaracion("La bomba A.", historial)
    assert consulta is not None
    assert "bomba auxiliar A (CMP-02)" in consulta
    assert "CIR-02" in consulta
    assert "CMP-03" not in consulta


def test_no_da_por_resuelta_una_seleccion_ambigua():
    historial = [
        {"role": "user", "content": "¿Cómo compruebo la bomba auxiliar?"},
        {
            "role": "assistant",
            "content": "¿A cuál te refieres: bomba A (CMP-02) o bomba B (CMP-03)?",
            "clarification_kind": "technical",
        },
    ]
    assert consulta_autonoma_tras_aclaracion("No sé", historial) is None
