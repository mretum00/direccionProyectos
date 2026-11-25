"""Pasos observables del proceso RAG para mostrarlos en el chat.

Esta capa describe operaciones verificables del sistema: transformación de la
consulta, fragmentos recuperados, cobertura documental R07 y resultado final.
No expone ni solicita razonamiento interno privado del modelo.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .retrieval import documento_de

PERFILES = {"user": "Conductor", "mechanic": "Técnico de mantenimiento"}
_CODIGO_TECNICO = re.compile(
    r"\b(?:CMP|TES|CIR)-\d{2}\b|\bHTM-(?:TOOL-)?\d{2,4}\b|\bHTM240-[A-Z]{3}-\d{3}\b"
)
_TIPOS_POR_CODIGO = {
    "DTC": "dtc_catalog",
    "DIC": "glossary",
    "HIS": "historical_case",
    "SEG": "safety_manual",
    "DIA": "decision_tree",
}


def _normalizar_codigos(texto: str) -> str:
    return re.sub(r"(?<=[A-Z0-9])[‐‑‒–—−](?=[A-Z0-9])", "-", texto)


def _codigos(texto: str) -> list[str]:
    return list(dict.fromkeys(_CODIGO_TECNICO.findall(_normalizar_codigos(texto))))


def _referencia_fragmento(fragmento: dict[str, Any]) -> str:
    chunk_id = str(fragmento.get("chunk_id", ""))
    documento = documento_de(chunk_id) if chunk_id else "Documento desconocido"
    match = re.match(r"(HTM240-[A-Z]{3}-\d{3})", documento)
    codigo = match.group(1) if match else documento
    pagina = fragmento.get("pagina")
    return f"{codigo} · pág. {pagina}" if pagina is not None else codigo


def comprobacion(texto: str, estado: str) -> dict[str, Any]:
    """Un resultado de las comprobaciones previas: "ok", "stop" (detiene) o "skipped"."""
    return {"text": texto, "status": estado}


def paso_comprobaciones(resultados: list[dict[str, Any]]) -> dict[str, Any]:
    """Fase 0: lo que se comprueba antes de buscar (versión, coherencia, ambigüedad).

    Si alguna comprobación detiene la consulta, el paso lo dice en su título: es el
    único paso de las respuestas de aclaración.
    """
    detenida = any(resultado.get("status") == "stop" for resultado in resultados)
    return {
        "kind": "checks",
        "title": "Comprobaciones previas: falta un dato" if detenida else "Comprobaciones previas superadas",
        "detail": (
            "La consulta se detuvo antes de buscar en la documentación para pedirte una aclaración."
            if detenida
            else "Antes de buscar se comprueba que la consulta es coherente y concreta."
        ),
        "points": resultados,
    }


def paso_transformacion(
    version: str,
    perfil: str,
    original: str,
    reformulada: str,
    consulta_tecnica: str,
    fecha: datetime | None = None,
    aclaracion: str | None = None,
) -> dict[str, Any]:
    """Describe cómo se preparó la consulta para la búsqueda.

    `aclaracion` es la opción que eligió el usuario al responder a una aclaración
    técnica; entonces `reformulada` es su pregunta original con esa opción.
    """
    fecha = (fecha or datetime.now().astimezone()).astimezone()
    etapas: list[dict[str, Any]] = [{"label": "Pregunta original", "text": original}]

    if aclaracion:
        etapas.append({
            "label": "Aclaración aplicada",
            "text": aclaracion,
            "note": "Opción que has elegido en la aclaración anterior.",
        })
        etapas.append({
            "label": "Pregunta completa",
            "text": reformulada,
            "note": "Tu pregunta anterior con la opción elegida.",
        })
    elif reformulada != original:
        etapas.append({
            "label": "Reformulada con el historial",
            "text": reformulada,
            "note": "Se han resuelto referencias a mensajes anteriores para que la búsqueda sea autónoma.",
        })

    enriquecida = consulta_tecnica
    prefijo = f"{reformulada} ("
    if consulta_tecnica.startswith(prefijo) and consulta_tecnica.endswith(")"):
        enriquecida = consulta_tecnica[len(prefijo):-1].strip()
    enriquecida = _normalizar_codigos(enriquecida)

    if enriquecida and enriquecida != reformulada:
        anteriores = set(_codigos(reformulada))
        nuevos = [codigo for codigo in _codigos(enriquecida) if codigo not in anteriores]
        etapas.append({
            "label": "Consulta técnica para la búsqueda",
            "text": enriquecida,
            "terms": nuevos or None,
            "note": "Esta consulta se utiliza para recuperar documentación; la respuesta se redacta para la pregunta del usuario.",
        })
    else:
        etapas.append({
            "label": "Consulta utilizada para la búsqueda",
            "text": reformulada,
            "note": "No se añadieron términos técnicos adicionales.",
        })

    return {
        "kind": "query",
        "title": "Preparación de la consulta",
        "detail": (
            f"Versión {version} · Perfil {PERFILES.get(perfil, perfil).lower()} · "
            f"Consulta realizada el {fecha:%d/%m/%Y} a las {fecha:%H:%M:%S}"
        ),
        "stages": etapas,
    }


def paso_busqueda(
    version: str,
    fragmentos: list[dict[str, Any]],
    ids_utilizados: set[str] | None,
) -> dict[str, Any]:
    """Resume los fragmentos recuperados y cuáles acabaron citándose en la respuesta."""
    utilizados = ids_utilizados or set()
    recuperados = len(fragmentos)
    usados = len(utilizados)
    detalle = f"{recuperados} fragmento(s) recuperado(s) para {version}"
    if ids_utilizados is not None:
        detalle += f" · {usados} citado(s) en la respuesta"

    filas = []
    for fragmento in fragmentos:
        chunk_id = str(fragmento.get("chunk_id", ""))
        if not chunk_id:
            continue
        documento = documento_de(chunk_id)
        match = re.match(r"HTM240-([A-Z]{3})-\d{3}", documento)
        source_type = _TIPOS_POR_CODIGO.get(match.group(1), "manual") if match else "manual"
        filas.append({
            "document": match.group(0) if match else documento,
            "source_type": source_type,
            "page": fragmento.get("pagina"),
            "section": fragmento.get("seccion"),
            "score": round(float(fragmento.get("score", 0.0)), 3),
            "used": chunk_id in utilizados,
            "note": fragmento.get("nota_version"),
        })

    return {
        "kind": "search",
        "title": f"Búsqueda documental de {version}",
        "detail": detalle,
        "fragments": filas,
    }


def paso_cobertura(suficiencia: dict[str, Any] | None) -> dict[str, Any] | None:
    """Expone los resultados estructurados de R07, nunca el razonamiento del LLM."""
    if not suficiencia or suficiencia.get("status") in {None, "not_run"}:
        return None

    estado = suficiencia.get("status", "unavailable")
    titulos = {
        "sufficient": "Cobertura documental completa",
        "partial": "Cobertura documental parcial",
        "insufficient": "Datos solicitados no localizados",
        "unavailable": "Comprobación de cobertura no disponible",
    }
    puntos = []
    for item in suficiencia.get("requested_items", []):
        item_estado = item.get("status", "uncertain")
        if item_estado == "supported":
            texto = f"Dato respaldado por una cita localizada: {item.get('item', 'dato solicitado')}"
        elif item_estado == "not_found":
            texto = f"Dato no localizado: {item.get('item', 'dato solicitado')}"
        elif item_estado == "conflicting":
            texto = f"Se encontraron datos contradictorios para: {item.get('item', 'dato solicitado')}"
        else:
            texto = f"No se pudo determinar la cobertura de: {item.get('item', 'dato solicitado')}"

        refs = []
        for source_id in item.get("source_ids", []):
            # R07 ya valida localmente que el identificador pertenezca a un fragmento.
            # El ID se convierte aquí a una referencia legible sin exponer texto interno.
            if source_id:
                base = str(source_id).rsplit("_", 1)[0]
                match = re.match(r"(HTM240-[A-Z]{3}-\d{3})", base)
                refs.append(match.group(1) if match else base)
        puntos.append({"text": texto, "refs": list(dict.fromkeys(refs)) or None})

    if estado == "unavailable":
        detalle = "No fue posible comprobar la cobertura documental; por seguridad no se generó una respuesta técnica."
    else:
        respaldados = sum(1 for item in suficiencia.get("requested_items", []) if item.get("status") == "supported")
        total = len(suficiencia.get("requested_items", []))
        detalle = f"{respaldados} de {total} datos solicitados tienen evidencia localizada y validada."

    if not puntos and estado == "unavailable":
        puntos.append({"text": detalle})

    return {
        "kind": "analysis",
        "title": titulos.get(estado, "Comprobación de cobertura documental"),
        "detail": detalle,
        "points": puntos or None,
    }


def paso_conclusion(
    evidencia: str,
    mejor_score: float,
    umbral_minimo: float,
    umbral_alto: float,
    *,
    fuentes: int = 0,
    documentos: int = 0,
    detalle_extra: str | None = None,
) -> dict[str, Any]:
    """Describe el resultado y los umbrales aplicados."""
    if evidencia == "insufficient":
        titulo = "Evidencia insuficiente"
        motivo = detalle_extra or f"No se ha autorizado una respuesta técnica (mejor similitud: {mejor_score:.2f}; mínimo: {umbral_minimo:.2f})."
    elif evidencia == "high":
        titulo = "Evidencia alta"
        motivo = f"Mejor similitud {mejor_score:.2f} (umbral alto: {umbral_alto:.2f})."
    else:
        titulo = "Evidencia media"
        motivo = f"Mejor similitud {mejor_score:.2f} (umbral mínimo: {umbral_minimo:.2f})."

    if evidencia != "insufficient":
        motivo += f" Se citaron {fuentes} fragmento(s) de {documentos} documento(s)."

    return {"kind": "conclusion", "evidence": evidencia, "title": titulo, "detail": motivo}
