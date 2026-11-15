"""
Recuperación: leer los fragmentos de la BD y buscar los más parecidos a la consulta.

- documento_de: nombre del documento al que pertenece un fragmento.
- cargar_fragmentos: lee todos los fragmentos de la tabla rag_documents.
- buscar_fragmentos: devuelve los top_k fragmentos más parecidos a la consulta
  para la versión del motor elegida.
"""

import json
import re

import numpy as np

from config import settings
from db.repositories import RagChunkRepository

from .embeddings import embedding_normalizado

# Acceso a la tabla de fragmentos (rag_documents).
rag_chunk_repository = RagChunkRepository()


def documento_de(chunk_id: str) -> str:
    """Nombre del documento al que pertenece un fragmento: "Manual.pdf_12" -> "Manual.pdf"."""
    return chunk_id.rsplit("_", 1)[0]


def _normalizar_guiones(texto: str) -> str:
    """Unifica los guiones raros que salen de los PDF o del LLM ("HTM‑0142" -> "HTM-0142")."""
    return re.sub(r"[‐-―−]", "-", texto)


def cargar_fragmentos() -> list[dict]:
    """Lee todos los fragmentos de la tabla rag_documents (BD en settings.db_path).

    Se lee la BD en cada llamada (sin caché), así que si se regenera se usa
    siempre la versión actual sin reiniciar el servidor.
    Devuelve una lista de dicts: {"chunk_id", "texto", "categoria", "versiones",
    "vector", "pagina", "seccion"}. "pagina" es la página del PDF donde empieza el
    fragmento y "seccion" el código del caso de servicio (None si no aplica).
    """
    fragmentos = []
    for fila in rag_chunk_repository.list_all():
        fragmentos.append({
            "chunk_id": fila.chunk_id,
            "texto": fila.text,
            "categoria": fila.category,
            # SQLite no guarda listas: viene como texto JSON '["V1.0"]' -> ["V1.0"].
            "versiones": json.loads(fila.applicable_versions or "[]"),
            # En SQLite el embedding está guardado como bytes: se convierten a números.
            # Ya vienen normalizados desde el generador.
            "vector": np.frombuffer(fila.embedding or b"", dtype=np.float32),
            "pagina": fila.page,
            "seccion": fila.section,
        })

    return fragmentos


def buscar_fragmentos(consulta_tecnica: str, version: str, top_k: int) -> list[dict]:
    """Devuelve los top_k fragmentos más parecidos a la consulta para esa versión.

    Cada resultado es {"chunk_id", "texto", "categoria", "score", "versiones",
    "pagina", "seccion"}, ordenados de mayor a menor score. Lista vacía si no hay ninguno.
    """
    fragmentos = cargar_fragmentos()
    vector_pregunta = embedding_normalizado(consulta_tecnica)

    # Los embeddings no distinguen bien un código de otro ("HTM-0142" vs "HTM-0124"),
    # así que si la consulta menciona códigos de avería, los fragmentos que contienen
    # exactamente ese código reciben un extra en la puntuación.
    codigos = set(re.findall(r"HTM-\d{4}", _normalizar_guiones(consulta_tecnica).upper()))

    resultados = []

    for f in fragmentos:
        # El glosario solo sirve para traducir la consulta, no como respuesta.
        if f["categoria"] == "Dictionary":
            continue
        # Nunca devolver documentos de otra versión del motor.
        if version not in f["versiones"]:
            continue

        # Ambos vectores miden 1, así que el producto escalar es la similitud coseno.
        score = float(np.dot(f["vector"], vector_pregunta))
        if codigos and any(c in _normalizar_guiones(f["texto"]) for c in codigos):
            score += settings.rag_code_match_bonus
        resultados.append({
            "chunk_id": f["chunk_id"],
            "texto": f["texto"],
            "categoria": f["categoria"],
            "score": score,
            "versiones": f["versiones"],
            "pagina": f["pagina"],
            "seccion": f["seccion"],
        })

    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados[:top_k]