"""La versión elegida en la interfaz no se vuelve a pedir ni se mezcla con la de otros mensajes."""

from services.prompts import construir_prompt, formatear_historial
from services.respuestas import pedir_aclaracion


def test_el_historial_indica_la_version_de_cada_mensaje():
    historial = [
        {"role": "user", "content": "¿Intervalo de refrigerante?", "engine_version": "V1.0"},
        {"role": "assistant", "content": "60.000 km", "engine_version": "V1.0"},
        {"role": "user", "content": "¿Y la bomba?"},
    ]
    assert formatear_historial(historial) == (
        "Usuario [V1.0]: ¿Intervalo de refrigerante?\nAsistente [V1.0]: 60.000 km\nUsuario: ¿Y la bomba?"
    )


def test_el_prompt_da_por_conocida_la_version_elegida():
    prompt = construir_prompt("¿Cuál es el intervalo de mantenimiento de mi versión?", [], "user", [], "V1.1")
    assert "NUNCA pidas al usuario que confirme o indique su versión" in prompt
    assert "EXPÓN LOS DATOS DE TODAS LAS VERSIONES" not in prompt


def test_sin_version_solo_se_pide_la_version_no_el_perfil():
    texto = pedir_aclaracion("")["message"]["content"]
    assert "versión del motor" in texto
    assert "tipo de usuario" not in texto
