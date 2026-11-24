"""Pruebas unitarias de la capa determinista de seguridad."""

from services.safety import evaluar_alertas_seguridad


def test_detecta_dtc_de_sobretemperatura():
    alertas = evaluar_alertas_seguridad("¿Qué significa el código HTM-0101?")

    assert [alerta["code"] for alerta in alertas] == ["engine_overheating"]
    assert alertas[0]["severity"] == "critical"


def test_detecta_testigo_de_alta_tension():
    alertas = evaluar_alertas_seguridad("Se ha encendido el testigo TES-05 rojo")

    assert [alerta["code"] for alerta in alertas] == ["high_voltage"]
    assert alertas[0]["severity"] == "critical"


def test_detecta_fuga_en_componente_de_alta_tension():
    alertas = evaluar_alertas_seguridad("Hay una fuga en el componente CMP-12")

    assert [alerta["code"] for alerta in alertas] == ["high_voltage"]


def test_detecta_mencion_de_vehiculo_real():
    alertas = evaluar_alertas_seguridad("Quiero reparar mi coche real con este procedimiento")

    assert [alerta["code"] for alerta in alertas] == ["real_vehicle"]
    assert alertas[0]["severity"] == "warning"


def test_detecta_riesgo_mencionado_en_el_seguimiento():
    historial = [
        {"role": "user", "content": "Está saliendo humo y huele a quemado"},
        {"role": "assistant", "content": "¿Puedes indicar la versión?"},
    ]

    alertas = evaluar_alertas_seguridad("¿Qué hago ahora?", historial)

    assert any(alerta["code"] == "high_voltage" for alerta in alertas)


def test_no_muestra_alerta_para_consulta_tecnica_normal():
    alertas = evaluar_alertas_seguridad("¿Qué función tiene el componente CMP-05?")

    assert alertas == []


def test_puede_devolver_aviso_educativo_y_critico_a_la_vez():
    alertas = evaluar_alertas_seguridad(
        "Mi coche real tiene encendido el testigo TES-05"
    )

    codigos = {alerta["code"] for alerta in alertas}
    assert codigos == {"real_vehicle", "high_voltage"}


def test_detecta_tes01_rojo_parpadeante_como_sobrecalentamiento_critico():
    alertas = evaluar_alertas_seguridad(
        "El testigo TES-01 está rojo y parpadea."
    )

    assert [alerta["code"] for alerta in alertas] == ["engine_overheating"]
    assert alertas[0]["severity"] == "critical"


def test_tes01_amarillo_fijo_no_activa_alerta_critica_de_parada():
    alertas = evaluar_alertas_seguridad(
        "El testigo TES-01 está amarillo fijo."
    )

    assert alertas == []
