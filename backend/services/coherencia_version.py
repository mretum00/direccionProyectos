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
from uuid import uuid4

from config import ENGINE_VERSIONS

# Exige un prefijo explícito (V1.0 o "versión 1.0") para no confundir
# decimales, tolerancias o valores técnicos con versiones del sistema.
_PATRON_VERSION = re.compile(
    r"(?<![A-Z0-9])(?:"
    r"V\s*(?P<major_v>\d{1,2})\s*[.,]\s*(?P<minor_v>\d{1,2})"
    r"|"
    r"VERSI[ÓO]N(?:\s+DEL\s+(?:MOTOR|SISTEMA|VEH[IÍ]CULO))?\s+"
    r"(?:V\s*)?(?P<major_text>\d{1,2})\s*[.,]\s*(?P<minor_text>\d{1,2})"
    r")(?!\d)",
    re.IGNORECASE,
)


def extraer_versiones_mencionadas(texto: str) -> list[str]:
    """Devuelve versiones explícitas y únicas, conservando el orden de aparición.

    Acepta, por ejemplo, "V1.0", "v 1,0" y "versión 2.0". No interpreta
    números decimales sin prefijo como versiones.
    """
    encontradas: list[str] = []
    for coincidencia in _PATRON_VERSION.finditer(texto or ""):
        major = coincidencia.group("major_v") or coincidencia.group("major_text")
        minor = coincidencia.group("minor_v") or coincidencia.group("minor_text")
        version = f"V{int(major)}.{int(minor)}"
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
    versiones = extraer_versiones_mencionadas(mensaje)
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
    seleccionada = (version_seleccionada or "").strip().upper()
    if mencionada == seleccionada:
        return None

    if mencionada not in versiones_soportadas:
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
    return {
        "message": {
            "id": str(uuid4()),
            "role": "assistant",
            "content": incoherencia["message"],
        },
        "evidence_status": "insufficient",
        "needs_clarification": True,
        "clarification_kind": incoherencia["kind"],
        "sources": [],
        "documents_consulted": 0,
        "safety_alerts": alertas_seguridad or [],
    }
