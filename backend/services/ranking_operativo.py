"""Reordenación operativa anclada a códigos de componente CMP.

Esta señal solo cambia el orden de recuperación. No modifica score,
ranking_score ni rrf_score, que conservan su significado original.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_COMPONENT_RE = re.compile(
    r"(?<![A-Z0-9])CMP[-‐‑‒–—−]?(\d{2})(?!\d)",
    re.IGNORECASE,
)
_CODIGO_HTM_RE = re.compile(
    r"(?<![A-Z0-9])HTM[-‐‑‒–—−]\d{4}(?!\d)",
    re.IGNORECASE,
)
_ACTION_SECTIONS = {
    "pasos",
    "valores esperados",
    "criterios de aceptacion",
    "verificacion final",
}
# Raíces de los verbos de acción en cualquier persona: "compruebo", "reviso",
# "verifico", "mido"... (antes solo se reconocían infinitivo e imperativo, así que
# "¿Cómo compruebo la bomba CMP-02?" no recibía los pasos del procedimiento).
_ACTION_TERMS_RE = re.compile(
    r"\b(comprob|comprueb|verific|realiz|ejecut|medir|mid[oaei]|probar|prueb|inspeccion|revis)\w*"
)


def normalizar(texto: str) -> str:
    """Normaliza minúsculas y elimina tildes para comparar texto español."""
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(caracter) != "Mn"
    )


def codigos_componente(texto: str) -> set[str]:
    """Extrae referencias CMP-XX y normaliza variantes de guion."""
    return {
        f"CMP-{coincidencia}"
        for coincidencia in _COMPONENT_RE.findall(texto or "")
    }


def codigos_htm(texto: str) -> set[str]:
    """Extrae códigos HTM-XXXX completos para conservar su prioridad."""
    return {
        re.sub(r"[-‐‑‒–—−]", "-", coincidencia.upper())
        for coincidencia in _CODIGO_HTM_RE.findall(texto or "")
    }


def es_consulta_procedimental(consulta: str) -> bool:
    """Solo activa el anclaje en preguntas explícitas de cómo realizar una acción."""
    texto = normalizar(consulta)
    pregunta_como = bool(re.search(r"\b(como|de que manera)\b", texto))
    accion = bool(_ACTION_TERMS_RE.search(texto))
    return pregunta_como and accion


def es_seccion_operativa(seccion: str) -> bool:
    """Identifica apartados con instrucciones o criterios de comprobación."""
    seccion_norm = normalizar(seccion).strip()
    if seccion_norm in _ACTION_SECTIONS:
        return True
    # Apartado específico del manual de diagnóstico del electroventilador.
    return bool(re.match(r"4\.5\s+electroventilador", seccion_norm))


def documento_de_resultado(resultado: dict[str, Any]) -> str:
    """Devuelve el nombre del PDF a partir del identificador del fragmento."""
    chunk_id = str(resultado.get("chunk_id") or "")
    return chunk_id.rsplit("_", 1)[0]


def documentos_anclados(
    resultados: list[dict[str, Any]],
    codigos: set[str],
) -> set[str]:
    """Localiza documentos que mencionan explícitamente algún CMP consultado."""
    if not codigos:
        return set()

    anclados: set[str] = set()
    for resultado in resultados:
        contenido = " ".join((
            str(resultado.get("texto") or ""),
            str(resultado.get("seccion") or ""),
            str(resultado.get("chunk_id") or ""),
        ))
        if codigos.intersection(codigos_componente(contenido)):
            anclados.add(documento_de_resultado(resultado))
    return anclados


def reordenar_con_anclaje(
    consulta: str,
    resultados: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Prioriza secciones operativas en documentos anclados a un CMP consultado.

    Condiciones:
    - La consulta debe pedir explícitamente cómo realizar una acción.
    - Debe contener un código CMP-XX.
    - El documento debe mencionar ese mismo código en alguno de sus fragmentos.
    - Secciones operativas: Pasos, Valores esperados, Criterios de aceptación,
      Verificación final y 4.5 Electroventilador.

    La coincidencia DTC exacta mantiene prioridad absoluta.
    Las puntuaciones score, ranking_score y rrf_score no se modifican.
    """
    if not resultados:
        return [], {
            "codigos_componente": [],
            "consulta_procedimental": False,
            "documentos_anclados": [],
        }

    codigos = codigos_componente(consulta)
    procedimental = es_consulta_procedimental(consulta)
    docs_anclados = (
        documentos_anclados(resultados, codigos)
        if codigos and procedimental
        else set()
    )
    codigos_consulta_htm = codigos_htm(consulta)

    def clave(resultado: dict[str, Any]) -> tuple[bool, bool, float, float]:
        documento = documento_de_resultado(resultado)
        seccion_operativa_anclada = (
            documento in docs_anclados
            and es_seccion_operativa(str(resultado.get("seccion") or ""))
        )
        dtc_exacto = (
            resultado.get("categoria") == "DTC"
            and bool(codigos_consulta_htm.intersection(
                codigos_htm(str(resultado.get("seccion") or ""))
            ))
        )
        return (
            dtc_exacto,
            seccion_operativa_anclada,
            float(resultado.get("rrf_score", 0.0)),
            float(resultado.get("ranking_score", 0.0)),
        )

    ordenados = sorted(resultados, key=clave, reverse=True)
    diagnostico = {
        "codigos_componente": sorted(codigos),
        "consulta_procedimental": procedimental,
        "documentos_anclados": sorted(docs_anclados),
    }
    return ordenados, diagnostico
