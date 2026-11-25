"""
Recuperación: leer los fragmentos de la BD y buscar los más parecidos a la consulta.

- documento_de: nombre del documento al que pertenece un fragmento.
- cargar_fragmentos: lee todos los fragmentos de la tabla rag_documents.
- buscar_fragmentos: devuelve los top_k fragmentos más parecidos a la consulta
  para la versión del motor elegida.

Cuando la consulta incluye un código HTM concreto, el orden también tiene en
cuenta la coincidencia exacta de ese código en la sección del fragmento. La
puntuación semántica original se conserva por separado para no inflar el nivel
 de evidencia del pipeline.
"""

import json
import re

import numpy as np

from config import settings
from db.repositories import RagChunkRepository

from .embeddings import embedding_normalizado
from .ranking_hibrido import ordenar_hibrido
from .ranking_operativo import reordenar_con_anclaje
from .ranking_combinado import seleccionar_combinada

# Acceso a la tabla de fragmentos (rag_documents).
rag_chunk_repository = RagChunkRepository()

# Coincidencia completa de códigos HTM-XXXX. Evita aceptar, por ejemplo,
# HTM-0101 dentro de HTM-01010.
_PATRON_CODIGO_HTM = re.compile(r"(?<![A-Z0-9])HTM-\d{4}(?!\d)")
_PATRON_CODIGO_EN_TITULO = re.compile(
    r"(?:C[OÓ]DIGO|DTC)\s*[:#-]?\s*(HTM-\d{4})",
    re.IGNORECASE,
)

# Evita que una misma fuente ocupe casi todas las posiciones del contexto.
# Se permiten dos fragmentos del mismo documento porque algunos contenidos
# (por ejemplo, una entrada DTC larga) se dividen en fragmentos complementarios.
_MAX_FRAGMENTOS_POR_DOCUMENTO = 2


def documento_de(chunk_id: str) -> str:
    """Nombre del documento al que pertenece un fragmento: "Manual.pdf_12" -> "Manual.pdf"."""
    return chunk_id.rsplit("_", 1)[0]


def _normalizar_guiones(texto: str) -> str:
    """Unifica los guiones raros que salen de los PDF o del LLM ("HTM‑0142" -> "HTM-0142")."""
    return re.sub(r"[‐-―−]", "-", texto)


def _extraer_codigos_htm(texto: str) -> set[str]:
    """Extrae códigos HTM-XXXX completos, normalizando variantes de guion."""
    normalizado = _normalizar_guiones(texto or "").upper()
    return set(_PATRON_CODIGO_HTM.findall(normalizado))


def _es_entrada_de_otro_codigo(fragmento: dict, codigos_consulta: set[str]) -> bool:
    """Detecta fragmentos que describen explícitamente otro código HTM.

    Solo se usa como filtro cuando la búsqueda sí ha encontrado la entrada DTC
    exacta del código solicitado. Así no se descartan documentos por una
    coincidencia parcial cuando el código consultado no existe en el catálogo.
    """
    if not codigos_consulta:
        return False

    codigos_seccion = _extraer_codigos_htm(fragmento.get("seccion") or "")

    # En el catálogo, la sección identifica la entrada concreta. Otra sección
    # DTC no debe ocupar una posición de una consulta por código exacto.
    if fragmento.get("categoria") == "DTC" and codigos_seccion:
        return not bool(codigos_consulta.intersection(codigos_seccion))

    texto = fragmento.get("texto") or ""
    codigos_texto = _extraer_codigos_htm(texto)
    encabezado = _normalizar_guiones(texto[:220]).upper()
    codigos_titulo = set(_PATRON_CODIGO_EN_TITULO.findall(encabezado))

    # Excluir boletines cuyo título identifica otro código y que no mencionan
    # el código consultado en ninguna parte del fragmento. Un manual general
    # que mencione códigos relacionados en su contenido no se descarta por ello.
    return bool(
        codigos_titulo
        and not codigos_consulta.intersection(codigos_titulo)
        and not codigos_consulta.intersection(codigos_texto)
    )


def _ajuste_orden_codigo(fragmento: dict, codigos_consulta: set[str]) -> float:
    """Calcula un ajuste SOLO para ordenar resultados de consultas con código.

    La coincidencia exacta en la sección recibe la prioridad más alta. Una
    coincidencia en el título con otro código se penaliza más que una mera
    coincidencia semántica. El ajuste nunca se incorpora a `score`, que sigue
    siendo la similitud coseno usada para valorar la evidencia.
    """
    if not codigos_consulta:
        return 0.0

    bonus = settings.rag_code_match_bonus
    codigos_seccion = _extraer_codigos_htm(fragmento.get("seccion") or "")
    texto = fragmento.get("texto") or ""
    codigos_texto = _extraer_codigos_htm(texto)
    encabezado = _normalizar_guiones(texto[:220]).upper()
    codigos_titulo = set(_PATRON_CODIGO_EN_TITULO.findall(encabezado))

    if codigos_consulta.intersection(codigos_seccion):
        return bonus * 2

    if fragmento.get("categoria") == "DTC" and codigos_seccion:
        return -bonus * 2

    if codigos_titulo and not codigos_consulta.intersection(codigos_titulo):
        # Si es un boletín de otro código que menciona el solicitado como
        # referencia secundaria, conservarlo con menor prioridad.
        return -bonus if codigos_consulta.intersection(codigos_texto) else -bonus * 2

    if codigos_consulta.intersection(codigos_texto):
        return bonus

    return 0.0


def _limitar_fragmentos_por_documento(resultados: list[dict], top_k: int) -> list[dict]:
    """Selecciona los mejores resultados evitando que un PDF monopolice el top_k.

    No elimina fragmentos por similitud: solo limita a dos fragmentos por PDF.
    Si hay pocos documentos aplicables, puede devolver menos de `top_k`; es
    preferible mostrar menos fuentes distintas a rellenar con duplicados.
    """
    if top_k <= 0:
        return []

    seleccionados: list[dict] = []
    por_documento: dict[str, int] = {}

    for resultado in resultados:
        documento = documento_de(resultado["chunk_id"])
        cantidad = por_documento.get(documento, 0)
        if cantidad >= _MAX_FRAGMENTOS_POR_DOCUMENTO:
            continue

        seleccionados.append(resultado)
        por_documento[documento] = cantidad + 1
        if len(seleccionados) >= top_k:
            break

    return seleccionados


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
    """Devuelve los top_k fragmentos relevantes para la versión seleccionada.

    `score` conserva la similitud coseno pura y se utiliza para evaluar evidencia.
    `ranking_score` incorpora señales léxicas de código y solo se utiliza para
    ordenar los resultados. Así una coincidencia de código ayuda a recuperar la
    ficha correcta, pero no aumenta artificialmente el nivel de evidencia.
    """
    fragmentos = cargar_fragmentos()
    vector_pregunta = embedding_normalizado(consulta_tecnica)
    codigos = _extraer_codigos_htm(consulta_tecnica)

    # Primero aplicar los filtros estructurales (categoría y versión).
    aplicables = [
        f for f in fragmentos
        if f["categoria"] != "Dictionary" and version in f["versiones"]
    ]

    # Si existe una entrada DTC exacta para el código consultado, evitamos que
    # otras entradas del catálogo o boletines dedicados a otro código ocupen
    # posiciones del contexto. Si el código no existe, no aplicamos este filtro:
    # el pipeline podrá valorar los resultados y responder con evidencia insuficiente.
    hay_dtc_exacto = bool(codigos) and any(
        f["categoria"] == "DTC"
        and codigos.intersection(_extraer_codigos_htm(f.get("seccion") or ""))
        for f in aplicables
    )
    if hay_dtc_exacto:
        aplicables = [
            f for f in aplicables
            if not _es_entrada_de_otro_codigo(f, codigos)
        ]

    resultados = []
    for f in aplicables:
        # Ambos vectores miden 1, así que el producto escalar es la similitud coseno.
        score = float(np.dot(f["vector"], vector_pregunta))
        ranking_score = score + _ajuste_orden_codigo(f, codigos)

        resultados.append({
            "chunk_id": f["chunk_id"],
            "texto": f["texto"],
            "categoria": f["categoria"],
            "score": score,
            # Campo interno de ranking; construir_fuentes no lo expone en la API.
            "ranking_score": ranking_score,
            "versiones": f["versiones"],
            "pagina": f["pagina"],
            "seccion": f["seccion"],
        })

    def clave_orden(resultado: dict) -> tuple[bool, float]:
        """La entrada DTC exacta siempre precede al contexto general.

        La similitud semántica puede favorecer mucho a un manual general que
        repita palabras de la consulta. Cuando existe una ficha DTC cuya sección
        coincide exactamente con el código solicitado, esa ficha debe aparecer
        primero; `ranking_score` ordena después los resultados de cada grupo.
        La puntuación semántica `score` no se modifica.
        """
        coincide_dtc_exacto = (
            resultado["categoria"] == "DTC"
            and bool(codigos.intersection(
                _extraer_codigos_htm(resultado.get("seccion") or "")
            ))
        )
        return coincide_dtc_exacto, resultado["ranking_score"]

    resultados.sort(key=clave_orden, reverse=True)

    # La recuperación híbrida es opcional durante la validación. Si está activa,
    # BM25 + RRF combina coincidencia léxica y semántica sin modificar `score`.
    # La prioridad estructural del DTC exacto se conserva como primera clave:
    # una coincidencia de texto nunca puede desplazar la ficha del código pedido.
    if settings.rag_hybrid_retrieval_enabled:
        resultados = ordenar_hibrido(
            consulta_tecnica,
            resultados,
            rrf_k=settings.rag_rrf_k,
        )
        resultados.sort(
            key=lambda resultado: (
                resultado["categoria"] == "DTC"
                and bool(codigos.intersection(
                    _extraer_codigos_htm(resultado.get("seccion") or "")
                )),
                float(resultado["rrf_score"]),
                float(resultado["ranking_score"]),
            ),
            reverse=True,
        )

    # Anclaje operativo opcional: en preguntas procedimentales con un código
    # CMP, adelanta secciones accionables de documentos que mencionan ese
    # componente. Se aplica antes del límite por documento para que los pasos
    # no queden fuera por fragmentos introductorios. No altera puntuaciones.
    if getattr(settings, "rag_component_anchor_enabled", False):
        resultados, _ = reordenar_con_anclaje(consulta_tecnica, resultados)

    # R03: reranking experimental COMBINADA. Se aplica sobre el ranking
    # completo y antes del límite normal de dos fragmentos por documento.
    # Las coincidencias CMP exactas pueden conservarse aunque varias fichas
    # pertenezcan al mismo PDF. La opción está desactivada por defecto.
    if getattr(settings, "rag_combined_reranking_enabled", False):
        return seleccionar_combinada(consulta_tecnica, resultados, top_k)

    return _limitar_fragmentos_por_documento(resultados, top_k)


def anadir_notas_de_alcance(consulta: str, resultados: list[dict], version: str) -> list[dict]:
    """Añade notas explícitas del diccionario que delimitan el alcance del corpus.

    La recuperación principal excluye Dictionary porque esas entradas sirven para
    reformular lenguaje coloquial, no para responder especificaciones. R07 sí debe
    conocer las exclusiones declaradas por el propio diccionario. Por ahora se añade
    la nota de A/C del habitáculo solo cuando la consulta trata expresamente ese
    subsistema; no se mezcla indiscriminadamente todo el glosario en el contexto.
    """
    consulta_normalizada = _normalizar_guiones(consulta or "").casefold()
    consulta_solicita_ac = bool(re.search(
        r"\b(?:aire\s+acondicionado|a/c|hvac|climatizador)\b",
        consulta_normalizada,
        flags=re.IGNORECASE,
    ))
    if not consulta_solicita_ac:
        return list(resultados)

    ids_existentes = {str(f.get("chunk_id", "")) for f in resultados}
    vector_pregunta = embedding_normalizado(consulta)
    enriquecidos = list(resultados)

    for fragmento in cargar_fragmentos():
        if fragmento.get("categoria") != "Dictionary":
            continue
        versiones = fragmento.get("versiones") or []
        if versiones and version not in versiones:
            continue

        texto = _normalizar_guiones(str(fragmento.get("texto", ""))).casefold()
        # Nota de alcance declarada por el corpus, no una inferencia del modelo.
        if "aire acondicionado" not in texto or "fuera del alcance" not in texto:
            continue

        chunk_id = str(fragmento.get("chunk_id", ""))
        if not chunk_id or chunk_id in ids_existentes:
            continue

        score = float(np.dot(fragmento["vector"], vector_pregunta))
        enriquecidos.append({
            "chunk_id": chunk_id,
            "texto": fragmento["texto"],
            "categoria": fragmento["categoria"],
            "score": score,
            "ranking_score": score,
            "versiones": versiones,
            "pagina": fragmento.get("pagina"),
            "seccion": fragmento.get("seccion"),
        })
        ids_existentes.add(chunk_id)

    return enriquecidos
