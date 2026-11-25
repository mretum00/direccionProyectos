"""Validación de coherencia entre la versión seleccionada y la mencionada.

La versión elegida en el selector identifica el vehículo/sistema que se está
consultando. Una versión escrita en la pregunta no debe cambiar ese contexto de
forma silenciosa. Si hay contradicción, se detiene el RAG y se pide confirmación.

Las consultas que mencionan varias versiones se identifican aparte: el recuperador
actual trabaja con una sola versión por turno y no debe responder una comparación
como si hubiera consultado ambas.
"""

from __future__ import annotations

import re
from typing import Any

from config import ENGINE_VERSIONS

from .respuestas import respuesta_aclaracion

# Exige un prefijo explícito (V1.0, v.2 o "versión 1.0") para no confundir
# decimales, tolerancias o valores técnicos con versiones del sistema.
_PATRON_VERSION = re.compile(
    r"(?<![A-Z0-9])(?:"
    # Completa con prefijo V: "V1.0", "v 1,0", "v.2.0".
    r"V(?:\.|\s*)(?P<major_v>\d{1,2})\s*[.,]\s*(?P<minor_v>\d{1,2})(?!\d)"
    r"|"
    # Completa con la palabra versión: "versión 2.0", "versión del motor v1.1".
    r"VERSI[ÓO]N(?:\s+DEL\s+(?:MOTOR|SISTEMA|VEH[IÍ]CULO))?\s+"
    r"(?:V\.?\s*)?(?P<major_text>\d{1,2})\s*[.,]\s*(?P<minor_text>\d{1,2})(?!\d)"
    r"|"
    # Solo la versión mayor, pegada a la V: "v2", "V.2". Sin espacio entre la V y el
    # número para no tomar "12 V 3 veces" como una versión.
    r"V\.?(?P<major_corta>\d{1,2})(?![0-9A-ZÁÉÍÓÚÑ])(?!\s*[.,]\s*\d)"
    r"|"
    # Solo la versión mayor con la palabra versión: "versión 2", "versión del motor 1".
    r"VERSI[ÓO]N(?:\s+DEL\s+(?:MOTOR|SISTEMA|VEH[IÍ]CULO))?\s+"
    r"(?:V\.?\s*)?(?P<major_texto_corta>\d{1,2})(?![0-9A-ZÁÉÍÓÚÑ])(?!\s*[.,]\s*\d)"
    r")",
    re.IGNORECASE,
)

# Sufijo de una versión mayor que corresponde a varias versiones documentadas
# (por ejemplo "v1" puede ser V1.0 o V1.1): "V1.x".
_SUFIJO_FAMILIA = ".x"


def _resolver_version_mayor(major: int, versiones_soportadas: tuple[str, ...]) -> str:
    """"v2" -> "V2.0" si es la única 2.x documentada; "v1" -> "V1.x" si hay varias."""
    candidatas = [v for v in versiones_soportadas if v.upper().startswith(f"V{major}.")]
    if len(candidatas) == 1:
        return candidatas[0]
    if candidatas:
        return f"V{major}{_SUFIJO_FAMILIA}"
    return f"V{major}"


def _candidatas_familia(version: str, versiones_soportadas: tuple[str, ...]) -> list[str]:
    """Versiones documentadas a las que puede referirse "V1.x"."""
    prefijo = version[: -len(_SUFIJO_FAMILIA)] + "."
    return [v for v in versiones_soportadas if v.upper().startswith(prefijo)]


def extraer_versiones_mencionadas(
    texto: str,
    versiones_soportadas: tuple[str, ...] = ENGINE_VERSIONS,
) -> list[str]:
    """Devuelve versiones explícitas y únicas, conservando el orden de aparición.

    Acepta, por ejemplo, "V1.0", "v 1,0", "versión 2.0", "v2", "v.2" y
    "versión 2". Una versión mayor sola se resuelve con las documentadas:
    "v2" -> "V2.0"; "v1" -> "V1.x" (puede ser V1.0 o V1.1). No interpreta
    números decimales sin prefijo como versiones.
    """
    encontradas: list[str] = []
    for coincidencia in _PATRON_VERSION.finditer(texto or ""):
        major = coincidencia.group("major_v") or coincidencia.group("major_text")
        minor = coincidencia.group("minor_v") or coincidencia.group("minor_text")
        if major is not None:
            version = f"V{int(major)}.{int(minor)}"
        else:
            major = coincidencia.group("major_corta") or coincidencia.group("major_texto_corta")
            version = _resolver_version_mayor(int(major), versiones_soportadas)
        if version not in encontradas:
            encontradas.append(version)
    return encontradas


def detectar_incoherencia_version(
    mensaje: str,
    version_seleccionada: str,
    versiones_soportadas: tuple[str, ...] = ENGINE_VERSIONS,
) -> dict[str, Any] | None:
    """Detecta discrepancias o consultas multi-versión antes de recuperar.

    - Cero versiones explícitas: el selector sigue siendo la fuente de verdad.
    - Una versión igual a la seleccionada: la consulta puede continuar.
    - Una versión distinta: solicita cambiar el selector o reformular la pregunta.
    - Dos o más versiones: bloquea la comparación porque el RAG actual consulta
      una única versión por turno.
    """
    seleccionada = (version_seleccionada or "").strip().upper()
    versiones: list[str] = []
    for version in extraer_versiones_mencionadas(mensaje, versiones_soportadas):
        # "v1" con V1.1 seleccionada es coherente: se refiere a la seleccionada.
        if version.endswith(_SUFIJO_FAMILIA) and seleccionada in _candidatas_familia(
            version, versiones_soportadas
        ):
            version = seleccionada
        if version not in versiones:
            versiones.append(version)
    if not versiones:
        return None

    if len(versiones) > 1:
        lista = ", ".join(versiones)
        disponibles = ", ".join(versiones_soportadas)
        return {
            "kind": "version_comparison",
            "versions": versiones,
            "message": (
                f"Tu pregunta menciona varias versiones ({lista}). Actualmente "
                "ThermoDrive consulta una sola versión por turno y todavía no "
                "realiza comparaciones directas entre versiones. Selecciona una "
                f"versión en el selector ({disponibles}) y vuelve a formular la "
                "pregunta para esa versión."
            ),
        }

    mencionada = versiones[0]
    if mencionada == seleccionada:
        return None

    if mencionada.endswith(_SUFIJO_FAMILIA):
        # "v1" con V2.0 seleccionada: no se sabe si es V1.0 o V1.1.
        mencionada = " o ".join(_candidatas_familia(mencionada, versiones_soportadas))
        detalle = (
            f"Has seleccionado {seleccionada} en el selector, pero tu pregunta "
            f"hace referencia a {mencionada}."
        )
    elif mencionada not in versiones_soportadas:
        detalle = (
            f"La versión mencionada ({mencionada}) no está entre las versiones "
            f"documentadas ({', '.join(versiones_soportadas)})."
        )
    else:
        detalle = (
            f"Has seleccionado {seleccionada} en el selector, pero tu pregunta "
            f"hace referencia a {mencionada}."
        )

    return {
        "kind": "version_mismatch",
        "versions": versiones,
        "selected_version": seleccionada,
        "mentioned_version": mencionada,
        "message": (
            f"{detalle} Para evitar mezclar procedimientos o valores de versiones "
            f"distintas, cambia el selector a {mencionada} si esa es la versión "
            f"que quieres consultar, o reformula la pregunta para {seleccionada}."
        ),
    }


def respuesta_aclaracion_version(
    incoherencia: dict[str, Any],
    alertas_seguridad: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Construye una respuesta de aclaración sin invocar embeddings ni Groq."""
    return respuesta_aclaracion(incoherencia["kind"], incoherencia["message"], alertas_seguridad)
