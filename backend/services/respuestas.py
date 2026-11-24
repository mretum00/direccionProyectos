"""
Lo que devuelve la API al frontend.

- construir_fuentes: convierte los fragmentos usados en fuentes (formato
  `Source` de models/schemas.py).
- respuesta_sin_evidencia: respuesta fija cuando no hay documentación que
  respalde una respuesta. No llama al LLM.
- pedir_aclaracion: pide al usuario que elija la versión del motor cuando falta
  o no existe. No llama al LLM.
"""

import re
import uuid

from config import ENGINE_VERSIONS, settings

from .retrieval import documento_de


# Tipo de documento (según su código, HTM240-XXX-001) -> tipo de fuente del contrato.
TIPOS_POR_CODIGO = {
    "DTC": "dtc_catalog",
    "DIC": "glossary",
    "HIS": "historical_case",
    "SEG": "safety_manual",
    "DIA": "decision_tree",
}


def _extracto(texto: str, limite: int) -> str:
    """Recorta el texto para la ficha de la fuente.

    Los fragmentos se solapan, así que muchos empiezan a mitad de frase
    (": HTM240-BOL-003;..."). Si es así, se salta hasta la primera viñeta o
    frase completa para que el extracto se lea bien.
    """
    # Empieza bien si lo hace con mayúscula, viñeta o numeración ("4.3 ", "2) ").
    empieza_bien = texto[:1].isupper() or texto[:1] in "•–" or re.match(r"\d+(\.\d+)*[.)]?\s+[A-ZÁÉÍÓÚ]", texto)
    if texto and not empieza_bien:
        cortes = [p for p in (texto.find("• "), texto.find(". ")) if 0 <= p < 200]
        if cortes:
            texto = texto[min(cortes):].lstrip(". ")
        else:
            # No hay dónde cortar: se indica que el texto empieza a medias.
            texto = "…" + texto
    # "..." solo si se ha cortado.
    return texto[:limite] + "..." if len(texto) > limite else texto


def extraer_referencias_citadas(texto_respuesta: str, total_fragmentos: int) -> set[int]:
    """Extrae los marcadores [F1], [F2] de la sección FUENTE y valida su rango.

    Los marcadores no se aceptan desde otras partes de la respuesta. Así, una mención
    casual dentro del resumen no convierte por sí sola un fragmento en fuente citada.
    Devuelve índices 1-based que corresponden al orden de fragmentos del prompt.
    """
    seccion = re.search(
        r"(?im)^#{1,6}\s*FUENTES?\s*$([\s\S]*?)(?=^#{1,6}\s+|\Z)",
        texto_respuesta,
    )
    if not seccion:
        return set()

    encontrados = re.findall(r"\[F(\d+)\]", seccion.group(1), flags=re.IGNORECASE)
    return {int(valor) for valor in encontrados if 1 <= int(valor) <= total_fragmentos}


def construir_fuentes(
    fragmentos: list[dict],
    version: str,
    referencias_citadas: set[int] | None = None,
) -> list[dict]:
    """Convierte los fragmentos en fuentes y distingue citas del contexto recuperado.

    `referencias_citadas` contiene índices 1-based validados contra el contexto entregado
    al modelo. Los fragmentos restantes se conservan como contexto recuperado, no como
    referencias declaradas por el asistente.
    """
    referencias_citadas = referencias_citadas or set()
    fuentes = []
    for indice, f in enumerate(fragmentos, start=1):
        chunk_id = f["chunk_id"]
        documento = documento_de(chunk_id)

        # Código del documento a partir del nombre: "HTM240-HIS-001_Casos..." -> "HTM240-HIS-001".
        codigo = re.match(r"HTM240-([A-Z]{3})-\d{3}", documento)

        # Tipo de fuente según el código del documento; si no se reconoce, manual.
        tipo = TIPOS_POR_CODIGO.get(codigo.group(1), "manual") if codigo else "manual"

        # Sección: código del documento y, en los casos de servicio, el código del caso.
        partes_seccion = [codigo.group(0)] if codigo else []
        if f.get("seccion"):
            partes_seccion.append(f["seccion"])

        fuentes.append({
            "id": chunk_id,
            "document": documento,
            "source_type": tipo,
            "section": " · ".join(partes_seccion) or None,
            # Página del PDF donde empieza el fragmento (None se omite en la respuesta).
            "page": f.get("pagina"),
            # Versiones a las que aplica el fragmento, no la elegida por el usuario.
            "engine_version": ", ".join(f.get("versiones") or [version]),
            "excerpt": _extracto(f["texto"], settings.source_excerpt_chars),
            "citation_status": "cited" if indice in referencias_citadas else "retrieved",
        })
    return fuentes


def respuesta_sin_evidencia() -> dict:
    """Respuesta fija cuando no hay documentación que respalde una respuesta."""
    return {
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": (
                "No hay información suficiente para responder a esta consulta. "
                "Se recomienda escalar la incidencia al equipo de soporte."
            ),
        },
        "evidence_status": "insufficient",
        "sources": [],
        "documents_consulted": 0
    }


def pedir_aclaracion(version_recibida: str) -> dict:
    """Pide al usuario que elija la versión del motor. No llama al LLM.

    El frontend, al ver `needs_clarification`, muestra el aviso con el botón
    que abre el selector de motor.
    """
    version_recibida = version_recibida.strip()
    opciones = ", ".join(ENGINE_VERSIONS)

    # Mensaje distinto si la versión venía rellena pero no existe, o si venía vacía.
    if version_recibida:
        texto = (
            f"No reconozco la versión «{version_recibida}». "
            f"¿Me dices cuál tienes? Elige una de estas: {opciones}."
        )
    else:
        texto = (
            "Antes de responderte necesito saber qué versión del motor tienes "
            f"({opciones}) y qué tipo de usuario eres (Mecánico o Usuario). "
            "Elígelos en el selector de motor."
        )

    return {
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": texto,
        },
        "needs_clarification": True,
        "sources": [],
        "documents_consulted": 0,
    }