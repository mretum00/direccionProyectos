"""
Pasos seguidos para llegar a una respuesta (campo `steps` de la API).

Cada paso es una fase del proceso con datos concretos, en el formato de
`ReasoningStep` (models/schemas.py):

  query           pregunta original -> (reformulada) -> consulta técnica generada
  search         cada fragmento recuperado con su similitud y si se ha usado o descartado
  analysis        el razonamiento del LLM sobre los fragmentos (sus propios pasos)
  conclusion      nivel de evidencia y por qué

El frontend (components/chat/ReasoningSteps.tsx) los dibuja como una línea temporal.
"""

import re
from datetime import datetime

from .respuestas import codigo_documento, extraer_referencias, normalizar_codigos, tipo_documento
from .retrieval import documento_de

# Nombre de cada perfil tal como se muestra al usuario.
PERFILES = {"user": "Conductor", "mechanic": "Técnico de mantenimiento"}

# Códigos técnicos que se destacan en la interpretación: componentes, testigos,
# circuitos, averías, herramientas y documentos.
_CODIGO_TECNICO = re.compile(r"\b(?:CMP|TES|CIR)-\d{2}\b|\bHTM-(?:TOOL-)?\d{2,4}\b|\bHTM240-[A-Z]{3}-\d{3}\b")


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _codigos(texto: str) -> list[str]:
    """Códigos técnicos de un texto, sin repetir y en orden de aparición."""
    return list(dict.fromkeys(_CODIGO_TECNICO.findall(normalizar_codigos(texto))))


def paso_transformacion(
    version: str,
    perfil: str,
    original: str,
    reformulada: str,
    consulta_tecnica: str,
    fecha: datetime | None = None,
) -> dict:
    """Fase 1: cómo se ha transformado la pregunta original en la consulta que se busca.

    `stages` va de la pregunta tal como la escribió el usuario a la consulta técnica
    generada, pasando por la reformulación con el historial si la ha habido.
    traducir_consulta devuelve "pregunta (pregunta enriquecida)": solo se muestra la
    parte enriquecida, que es la que genera el LLM.
    `detail` incluye siempre cuándo se ha hecho la consulta (`fecha`, por defecto ahora,
    en la hora local del servidor).
    """
    fecha = (fecha or datetime.now()).astimezone()
    etapas: list[dict] = [{"label": "Pregunta original", "text": original}]

    if reformulada != original:
        etapas.append({
            "label": "Reformulada con el historial",
            "text": reformulada,
            "note": "Sustituye las referencias a mensajes anteriores para que la pregunta se entienda sola.",
        })

    enriquecida = consulta_tecnica
    prefijo = f"{reformulada} ("
    if consulta_tecnica.startswith(prefijo) and consulta_tecnica.endswith(")"):
        enriquecida = consulta_tecnica[len(prefijo):-1].strip()
    enriquecida = normalizar_codigos(enriquecida)

    if enriquecida and enriquecida != reformulada:
        # Solo se destacan los códigos que no estaban ya en la pregunta.
        anteriores = set(_codigos(reformulada))
        nuevos = [c for c in _codigos(enriquecida) if c not in anteriores]
        etapas.append({
            "label": "Consulta técnica generada",
            "text": enriquecida,
            "terms": nuevos or None,
            "note": "Generada con el glosario. Solo se usa para buscar en la documentación: "
                    "el modelo responde a la pregunta original.",
        })
    else:
        etapas.append({
            "label": "Consulta técnica generada",
            "text": reformulada,
            "note": "El glosario no ha aportado términos técnicos: se busca con la pregunta tal cual.",
        })

    return {
        "kind": "query",
        "title": "Transformación de la consulta",
        "detail": (
            f"Versión {version} · Perfil {PERFILES.get(perfil, perfil).lower()}"
            f" · Consulta realizada el {fecha:%d/%m/%Y} a las {fecha:%H:%M:%S}"
        ),
        "stages": etapas,
    }


def paso_busqueda(version: str, fragmentos: list[dict], usados: list[dict] | None) -> dict:
    """Fase 3: cada fragmento recuperado, con su similitud y si se ha usado.

    `usados` es None cuando no se ha llegado a llamar al LLM (sin evidencia).
    """
    ids_usados = {f["chunk_id"] for f in usados or []}
    detalle = _plural(len(fragmentos), "fragmento recuperado", "fragmentos recuperados")
    if usados is not None:
        detalle += f" · {len(ids_usados)} usados en la respuesta"

    return {
        "kind": "search",
        "title": f"Búsqueda en la documentación de {version}",
        "detail": detalle,
        "fragments": [
            {
                "document": codigo_documento(documento_de(f["chunk_id"])),
                "source_type": tipo_documento(documento_de(f["chunk_id"])),
                "page": f.get("pagina"),
                "section": f.get("seccion"),
                "score": round(float(f.get("score", 0.0)), 3),
                "used": f["chunk_id"] in ids_usados,
            }
            for f in fragmentos
            if "chunk_id" in f
        ],
    }


def paso_razonamiento(puntos: list[str], fragmentos: list[dict]) -> dict | None:
    """Fase 4: los pasos que el propio LLM dice haber seguido (None si no los ha dado).

    Las referencias F1, F2... de cada punto se sacan del texto a `refs` ("HTM240-DIA-001 · pág. 1")
    para que el frontend las muestre como fichas y la frase no repita el documento.
    """
    if not puntos:
        return None
    detalle = []
    for punto in puntos:
        texto, citas = extraer_referencias(punto, fragmentos)
        if texto:
            detalle.append({"text": texto, "refs": citas or None})
    return {"kind": "analysis", "title": "Razonamiento sobre los fragmentos", "points": detalle} if detalle else None


def paso_conclusion(
    evidencia: str,
    mejor_score: float,
    umbral_minimo: float,
    umbral_alto: float,
    fuentes: int = 0,
    documentos: int = 0,
    llamo_al_modelo: bool = True,
) -> dict:
    """Fase 5: nivel de evidencia y en qué se basa."""
    if not llamo_al_modelo:
        return {
            "kind": "conclusion",
            "evidence": "insufficient",
            "title": "Sin evidencia suficiente",
            "detail": (
                f"La mejor similitud ({mejor_score:.2f}) no llega al mínimo de {umbral_minimo:.2f}: "
                "no se genera respuesta para no inventar datos y se recomienda escalar a soporte."
            ),
        }

    respaldo = (
        f"Respuesta respaldada por {_plural(fuentes, 'fragmento')} de {_plural(documentos, 'documento')}."
        if fuentes
        else "El modelo no ha usado ninguno de los fragmentos recuperados, así que no se muestran fuentes."
    )
    if evidencia == "insufficient":
        titulo, motivo = "Evidencia insuficiente", "El modelo indica que la documentación no basta para responder."
    elif evidencia == "high":
        titulo, motivo = "Evidencia alta", f"Mejor similitud {mejor_score:.2f} (≥ {umbral_alto:.2f})."
    else:
        titulo, motivo = "Evidencia media", f"Mejor similitud {mejor_score:.2f} (entre {umbral_minimo:.2f} y {umbral_alto:.2f})."

    return {"kind": "conclusion", "evidence": evidencia, "title": titulo, "detail": f"{motivo} {respaldo}"}
