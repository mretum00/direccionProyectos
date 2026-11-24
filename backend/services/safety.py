"""Controles deterministas de seguridad para consultas ThermoDrive.

Esta capa NO depende del prompt ni de la respuesta de Groq. Analiza el mensaje del
usuario (y las últimas intervenciones del propio usuario para entender seguimientos)
y devuelve avisos estructurados que el backend persiste con la respuesta y el frontend
muestra por separado del texto generado por el modelo.

Los avisos son preventivos y conservadores: no sustituyen la documentación oficial
ni generan procedimientos de reparación.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


_ALERTAS = {
    "real_vehicle": {
        "code": "real_vehicle",
        "severity": "warning",
        "title": "Documentación exclusivamente educativa",
        "message": (
            "ThermoDrive HTM-240 y sus manuales son ficticios y se han creado para este proyecto. "
            "No utilices esta respuesta para diagnosticar, mantener ni reparar un vehículo real. "
            "Consulta la documentación oficial del fabricante y a un profesional cualificado."
        ),
    },
    "high_voltage": {
        "code": "high_voltage",
        "severity": "critical",
        "title": "Posible riesgo eléctrico o térmico crítico",
        "message": (
            "Si esta situación está ocurriendo ahora, detén el vehículo en un lugar seguro y apaga "
            "el sistema solo si puedes hacerlo sin exponerte. No manipules cables, conectores, baterías "
            "ni componentes de alta tensión (300–400 V), ni manguitos; no intentes desconectar ni "
            "reparar el sistema. Si hay humo, fuego u olor a quemado, aléjate y solicita asistencia. "
            "La intervención debe realizarla personal habilitado siguiendo los procedimientos oficiales "
            "del fabricante (en el sistema ficticio del proyecto se indica Técnico Nivel 3)."
        ),
    },
    "engine_overheating": {
        "code": "engine_overheating",
        "severity": "critical",
        "title": "Aviso por posible sobrecalentamiento del motor",
        "message": (
            "Si el vehículo presenta ahora un aviso de temperatura elevada, detente en un lugar seguro "
            "y apaga el motor. No abras el depósito del refrigerante ni manipules manguitos o componentes "
            "calientes. Espera a que el sistema se enfríe por completo y solicita asistencia profesional "
            "si el aviso persiste. Para un vehículo real, sigue exclusivamente el procedimiento del "
            "fabricante: los datos y procedimientos de HTM-240 son ficticios y educativos."
        ),
    },
}


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas sin tildes y normaliza códigos/separadores a espacios."""
    descompuesto = unicodedata.normalize("NFKD", texto.casefold())
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sin_marcas).split())


def _contiene(texto: str, expresiones: Iterable[str]) -> bool:
    return any(expresion in texto for expresion in expresiones)


def _textos_usuario(mensaje: str, historial: list[dict] | None) -> str:
    """Incluye solo intervenciones del usuario para mantener contexto en seguimientos."""
    partes = [mensaje]
    anteriores = [
        str(item.get("content", ""))
        for item in (historial or [])
        if item.get("role") == "user" and item.get("content")
    ]
    # Limita el contexto para que una alerta antigua no permanezca indefinidamente.
    partes.extend(anteriores[-3:])
    return _normalizar(" ".join(partes))


def evaluar_alertas_seguridad(
    mensaje: str,
    historial: list[dict] | None = None,
) -> list[dict[str, str]]:
    """Devuelve avisos deterministas aplicables a una consulta.

    Señales contempladas, extraídas de las reglas de seguridad del proyecto:
    - uso/ reparación de un coche o vehículo real;
    - TES-05, humo, olor a quemado, alerta roja en modo tortuga, alta tensión o
      fugas en batería/componentes/circuitos de alta tensión;
    - HTM-0101 y expresiones directas de sobretemperatura del motor.

    No clasifica el nivel de evidencia ni modifica la recuperación documental.
    """
    texto = _textos_usuario(mensaje, historial)
    codigos: list[str] = []

    # El proyecto declara expresamente que HTM-240 es sintético y no debe usarse
    # para reparar vehículos reales.
    vehiculo_real = _contiene(
        texto,
        (
            "coche real",
            "vehiculo real",
            "auto real",
            "mi coche",
            "mi vehiculo",
            "mi auto",
            "vehiculo propio",
            "coche de verdad",
            "vehiculo de verdad",
        ),
    )
    if vehiculo_real:
        codigos.append("real_vehicle")

    # Los indicadores de peligro inmediato que el prompt del proyecto ya identifica.
    indicador_critico = _contiene(
        texto,
        (
            "tes 05",
            "humo",
            "olor a quemado",
            "olor quemado",
            "incendio",
            "fuego",
        ),
    )
    modo_tortuga_rojo = "modo tortuga" in texto and _contiene(
        texto, ("alerta roja", "testigo rojo", "aviso rojo")
    )
    alta_tension_explicita = _contiene(
        texto,
        (
            "testigo rojo de alta tension",
            "testigo rojo alta tension",
            "alta tension",
            "alto voltaje",
            "300 400v",
            "300 400 v",
            "300 400 voltios",
            "300v 400v",
        ),
    )
    fuga_bateria_alta_tension = _contiene(texto, ("fuga", "perdida", "filtracion")) and _contiene(
        texto,
        ("bateria", "cmp 10", "cmp 12", "cir 02", "cir 03", "alta tension", "alto voltaje"),
    )
    manipulacion_alta_tension = alta_tension_explicita and _contiene(
        texto,
        (
            "manipular", "tocar", "reparar", "desconectar", "cambiar", "sustituir",
            "desmontar", "medir", "comprobar", "revisar", "probar", "abrir",
        ),
    )

    if indicador_critico or modo_tortuga_rojo or fuga_bateria_alta_tension or manipulacion_alta_tension:
        codigos.append("high_voltage")

    # HTM-0101 es el DTC de sobretemperatura que aparece en el catálogo del proyecto.
    sobrecalentamiento = _contiene(
        texto,
        (
            "htm 0101",
            "sobretemperatura",
            "sobrecalentamiento",
            "motor se calienta",
            "motor demasiado caliente",
            "refrigerante hirviendo",
            "vapor del motor",
        ),
    )
    if not sobrecalentamiento and "temperatura del refrigerante" in texto:
        sobrecalentamiento = _contiene(texto, ("alta", "elevada", "118", "rojo", "sube"))
    if sobrecalentamiento:
        codigos.append("engine_overheating")

    return [dict(_ALERTAS[codigo]) for codigo in codigos]
