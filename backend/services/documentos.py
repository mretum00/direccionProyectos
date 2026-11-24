"""
Lista de documentos indexados (GET /api/documents).

La BD solo guarda fragmentos (tabla `rag_documents`), no una tabla de documentos. Cada fragmento
tiene un `chunk_id` con la forma "<archivo>.pdf_<n>", así que se reconstruye la lista agrupando
los fragmentos por archivo (igual que hace `documento_de` al citar fuentes).

- type:           se deduce del código del documento (HTM240-DTC-001 -> dtc_catalog...).
- engine_version: unión de las versiones de sus fragmentos ("Todas las versiones" si cubre todas).
- pages:          mayor página registrada entre los fragmentos del documento.
- uploaded_at:    la BD no guarda fecha por documento: se usa la de generación de la BD.
- status:         todo lo que está en la BD está procesado.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from config import ENGINE_VERSIONS, settings
from db.repositories import RagChunkRepository

from .respuestas import TIPOS_POR_CODIGO
from .retrieval import documento_de

repositorio = RagChunkRepository()

PATRON_CODIGO_DOC = re.compile(r"HTM240-([A-Z]{3})-\d{3}")


def _texto_versiones(versiones: set[str]) -> str:
    ordenadas = [v for v in ENGINE_VERSIONS if v in versiones]
    if set(ordenadas) == set(ENGINE_VERSIONS):
        return "Todas las versiones"
    return ", ".join(ordenadas)


def agrupar_documentos(filas, subido_en: str) -> list[dict]:
    """Agrupa los fragmentos (chunk_id, versiones JSON, página) por documento. Función pura: no toca la BD."""
    grupos: dict[str, dict] = {}

    for chunk_id, versiones_json, pagina in filas:
        nombre = documento_de(chunk_id)
        grupo = grupos.setdefault(nombre, {"versiones": set(), "paginas": 0})
        grupo["versiones"].update(json.loads(versiones_json or "[]"))
        grupo["paginas"] = max(grupo["paginas"], pagina or 0)

    documentos = []
    for nombre in sorted(grupos):
        codigo = PATRON_CODIGO_DOC.match(nombre)
        documentos.append({
            "id": nombre,
            "filename": nombre,
            "type": TIPOS_POR_CODIGO.get(codigo.group(1), "manual") if codigo else "manual",
            "engine_version": _texto_versiones(grupos[nombre]["versiones"]),
            "pages": grupos[nombre]["paginas"],
            "uploaded_at": subido_en,
            "status": "processed",
        })
    return documentos


def listar_documentos() -> list[dict]:
    """Documentos indexados en la BD, ordenados por nombre."""
    subido_en = datetime.fromtimestamp(settings.db_path.stat().st_mtime, tz=timezone.utc).isoformat()
    return agrupar_documentos(repositorio.list_summaries(), subido_en)

def ruta_pdf(nombre: str) -> Path | None:
    """Ruta del PDF con ese nombre dentro de la carpeta de manuales, o None si no existe.

    Se busca entre los PDF que hay en disco en vez de construir la ruta con el texto recibido:
    así nadie puede pedir "../../.env" y salirse de la carpeta de manuales.
    """
    for ruta in settings.manuals_dir.rglob("*.pdf"):
        if ruta.name == nombre:
            return ruta
    return None