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
        ("¿Qué caudal nominal tiene la bomba?", "pump_variant"),
        ("¿Cómo reviso la bomba?", "pump_variant"),
        ("¿Cómo compruebo la bomba?", "pump_variant"),
        ("¿Cómo reviso la bomba? El sensor CMP-15 da una lectura extraña.", "pump_variant"),
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
        "¿Qué caudal nominal tienen las tres bombas?",
        "¿Qué caudal nominal tiene la bomba auxiliar A CMP-02?",
        "¿Cómo compruebo la bomba auxiliar A CMP-02?",
        "¿Cómo reviso la bomba mecánica del motor CMP-01?",
        "¿Cómo reviso la bomba mecánica del motor?",
        "Compara el caudal de CMP-01, CMP-02 y CMP-03.",
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


@pytest.mark.parametrize(
    "respuesta,fragmento_esperado,fragmento_no_esperado",
    [
        ("La mecánica del motor", "CMP-01", "CMP-02"),
        ("La bomba A", "CMP-02", "CMP-03"),
        ("La bomba B", "CMP-03", "CMP-02"),
        ("CIR-01", "CMP-01", "CMP-02"),
    ],
)
def test_resuelve_aclaracion_entre_las_tres_bombas(respuesta, fragmento_esperado, fragmento_no_esperado):
    historial = [
        {"role": "user", "content": "¿Cómo reviso la bomba?"},
        {
            "role": "assistant",
            "content": (
                "¿A cuál bomba te refieres: CMP-01 (mecánica, CIR-01), "
                "CMP-02 (auxiliar A, CIR-02) o CMP-03 (auxiliar B, CIR-03)?"
            ),
            "clarification_kind": "technical",
        },
    ]

    consulta = consulta_autonoma_tras_aclaracion(respuesta, historial)

    assert consulta is not None
    assert fragmento_esperado in consulta
    assert fragmento_no_esperado not in consulta


def test_no_da_por_resuelta_la_aclaracion_general_de_bomba_con_respuesta_vaga():
    historial = [
        {"role": "user", "content": "¿Cómo reviso la bomba?"},
        {
            "role": "assistant",
            "content": (
                "¿A cuál bomba te refieres: CMP-01, CMP-02 o CMP-03?"
            ),
            "clarification_kind": "technical",
        },
    ]
    assert consulta_autonoma_tras_aclaracion("No sé", historial) is None


def _historial_aclaracion_testigo():
    return [
        {"role": "user", "content": "Se ha encendido un testigo rojo. ¿Debo detenerme?"},
        {
            "role": "assistant",
            "content": (
                "¿Qué código aparece: TES-01, TES-02 o TES-05? "
                "Si es TES-01 o TES-02, indica si está amarillo fijo o rojo parpadeante."
            ),
            "clarification_kind": "technical",
        },
    ]


def test_aclaracion_de_testigo_rojo_cubre_tes01_tes02_y_tes05():
    resultado = detectar_aclaracion_tecnica(
        "Se ha encendido un testigo rojo. ¿Debo detenerme?"
    )

    assert resultado is not None
    assert resultado["code"] == "red_indicator"
    for codigo in ("TES-01", "TES-02", "TES-05"):
        assert codigo in resultado["message"]
    assert "amarillo fijo" in resultado["message"]
    assert "rojo parpadeante" in resultado["message"]
    assert "siempre exige detención segura" in resultado["message"]


@pytest.mark.parametrize(
    "respuesta,fragmento_esperado",
    [
        ("TES-01 rojo parpadeante", "TES-01 de temperatura de motor, rojo parpadeante"),
        ("TES-02 amarillo fijo", "TES-02 de temperatura de batería de alta tensión, amarillo fijo"),
        ("TES-05", "TES-05 de alta tensión"),
    ],
)
def test_resuelve_aclaracion_de_testigo_con_codigo_y_estado(respuesta, fragmento_esperado):
    consulta = consulta_autonoma_tras_aclaracion(
        respuesta,
        _historial_aclaracion_testigo(),
    )

    assert consulta is not None
    assert fragmento_esperado in consulta


@pytest.mark.parametrize("respuesta", ["TES-01", "TES-01 rojo", "TES-02 amarillo", "TES-01 y TES-02 rojo parpadeante"])
def test_no_resuelve_testigo_si_falta_estado_o_hay_varios_codigos(respuesta):
    assert consulta_autonoma_tras_aclaracion(
        respuesta,
        _historial_aclaracion_testigo(),
    ) is None


def test_aclaracion_de_calefaccion_pregunta_las_condiciones_del_diagnostico_46():
    resultado = detectar_aclaracion_tecnica(
        "La calefacción no funciona. ¿Qué componente tengo que sustituir?"
    )

    assert resultado is not None
    assert "diagnóstico 4.6" in resultado["message"]
    assert "frío extremo" in resultado["message"]
    assert "temperaturas moderadas" in resultado["message"]
    assert "empeorado progresivamente" in resultado["message"]


def test_aclaracion_de_mantenimiento_da_ejemplos_con_identificadores_documentados():
    resultado = detectar_aclaracion_tecnica(
        "¿Cada cuánto tengo que hacer el mantenimiento?"
    )

    assert resultado is not None
    assert "CMP-24" in resultado["message"]
    assert "CMP-09" in resultado["message"]


def test_pregunta_nueva_tras_aclaracion_no_se_trata_como_respuesta():
    from services.ambiguedad import responde_a_aclaracion

    historial = [
        {"role": "user", "content": "¿Cómo reviso la bomba?"},
        {
            "role": "assistant",
            "content": "¿A cuál bomba te refieres: CMP-01, CMP-02 o CMP-03?",
            "clarification_kind": "technical",
        },
    ]
    assert responde_a_aclaracion("¿Qué significa el código HTM-0142?", historial) is False
    assert responde_a_aclaracion("No sé", historial) is True
    assert responde_a_aclaracion("La CMP-02", historial) is True


def test_aclaracion_repetida_conserva_la_pregunta_original():
    aclaracion = "¿A cuál bomba te refieres: CMP-01, CMP-02 o CMP-03?"
    historial = [
        {"role": "user", "content": "¿Cómo reviso la bomba?"},
        {"role": "assistant", "content": aclaracion, "clarification_kind": "technical"},
        {"role": "user", "content": "No sé"},
        {"role": "assistant", "content": aclaracion, "clarification_kind": "technical"},
    ]
    consulta = consulta_autonoma_tras_aclaracion("La CMP-02", historial)
    assert consulta is not None
    assert consulta.startswith("¿Cómo reviso la bomba?")
    assert "No sé" not in consulta
