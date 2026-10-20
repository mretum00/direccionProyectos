"""
Proceso de consulta RAG de ThermoDrive — esqueleto para repartir entre el equipo.

Reparto (4 personas):
  Persona A (integrador)       -> 1. validar_consulta, 8. armar_respuesta, 10. pedir_aclaracion
  Persona B (prompts)          -> 2. traducir_consulta, 5. construir_prompt
  Persona C (búsqueda vector.) -> 3. buscar_fragmentos, 4. cargar_fragmentos
  Persona D (LLM y salida)     -> 6. generar_respuesta, 7. construir_fuentes, 9. respuesta_sin_evidencia

Flujo completo (cada función es una tarea independiente):

  pregunta + versión
      -> 1. validar_consulta
      -> 2. traducir_consulta
      -> 3. buscar_fragmentos        (usa 4. cargar_fragmentos)
      -> 5. construir_prompt
      -> 6. generar_respuesta
      -> 7. construir_fuentes
      -> 8. armar_respuesta          (usa 9. respuesta_sin_evidencia / 10. pedir_aclaracion)

Dependencias para no bloquearse:
  - B necesita a C (glosario) y a D (LLM) para traducir_consulta: puede usar versiones falsas.
  - A deja armar_respuesta para el final, cuando existan las demás.
  - C y D pueden empezar ya.

Cada función indica qué recibe y qué devuelve para que se pueda trabajar en
paralelo sin esperar a los demás. Sin lógica de negocio: solo comentarios.
Este archivo es el que usa el endpoint POST /api/chat (controllers/chat_controller.py
llama a `armar_respuesta`). Mientras las funciones estén vacías, el endpoint
responde 501 "Pipeline RAG pendiente de implementar".

Configuración disponible (backend/config.py -> `from config import settings`):
  settings.db_path, settings.embedding_model, settings.groq_api_key,
  settings.llm_model, settings.llm_temperature, settings.rag_top_k,
  settings.rag_dictionary_top_k, settings.rag_dictionary_min_score,
  settings.source_excerpt_chars
Modelos del contrato de la API: models/schemas.py (ChatResponse, Source, ...).
"""

from typing import Optional
from sentence_transformers import SentenceTransformer
import logging
import uuid

from click import prompt
from config import settings

import json
import os
import sqlite3
import numpy as np

logger = logging.getLogger(__name__)
_modelo_embeddings = None

# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def _obtener_modelo():
    """Carga el modelo de embeddings una sola vez."""
    global _modelo_embeddings

    if _modelo_embeddings is None:
        _modelo_embeddings = SentenceTransformer(settings.embedding_model)

    return _modelo_embeddings

def _embedding_normalizado(texto: str) -> np.ndarray:
    """Conventir texto a emnbedding."""
    vector = _obtener_modelo().encode(texto, convert_to_numpy=True, show_progress_bar=False)
    vector = vector.astype(np.float32)
    return vector / (np.linalg.norm(vector) or 1.0)

# ---------------------------------------------------------------------------
# 1. Validar la consulta y la versión del motor           [Persona A]
# ---------------------------------------------------------------------------
def validar_consulta(mensaje: str, version: str, versiones_conocidas: list[str]) -> tuple[str, Optional[str]]:
    # Qué debe hacer:
    #   - Recortar espacios del mensaje y rechazarlo si queda vacío.
    #   - Comparar `version` con `versiones_conocidas` sin distinguir
    #     mayúsculas/minúsculas ni espacios (ej. " v2.0 " -> "V2.0").
    #   - Devolver (mensaje_limpio, version_canonica).
    #   - Si la versión está vacía o no existe, devolver version_canonica = None
    #     (así la capa superior sabrá que hay que pedir aclaración).
    pass


# ---------------------------------------------------------------------------
# 2. Traducir la consulta coloquial a lenguaje técnico    [Persona B]
# ---------------------------------------------------------------------------
def traducir_consulta(mensaje: str) -> str:
    try:
        fragmentos = cargar_fragmentos(str(settings.db_path))
        vector_mensaje = _embedding_normalizado(mensaje)

        terminos_relevantes = []
        for f in fragmentos:
            if f["categoria"] != "Dictionary":
                continue

            score = float(np.dot(f["vector"], vector_mensaje))
            if score >= settings.rag_dictionary_min_score:
                terminos_relevantes.append((score, f["texto"]))

        if not terminos_relevantes:
            return mensaje

        terminos_relevantes.sort(key=lambda x: x[0], reverse=True)
        mejores_terminos = [
            texto for _, texto in terminos_relevantes[:settings.rag_dictionary_top_k]
        ]

        glosario_contexto = "\n".join(f"- {t}" for t in mejores_terminos)

        prompt_traduccion = (
            "Eres un asistente técnico de automoción. Reescribe la siguiente consulta "
            "coloquial utilizando la terminología técnica oficial del glosario adjunto.\n"
            "Regla estricta: devuelve ÚNICAMENTE la consulta reescrita en una sola frase, "
            "sin introducciones, sin comillas y sin explicaciones adicionales.\n\n"
            f"Glosario aplicable:\n{glosario_contexto}\n\n"
            f"Consulta original: {mensaje}\n\n"
            "Consulta reescrita:"
        )

        consulta_reescrita = generar_respuesta(prompt_traduccion).strip()

        if not consulta_reescrita or "No hay evidencia suficiente" in consulta_reescrita:
            return mensaje

        return consulta_reescrita

    except Exception:
        logger.warning("Fallo al traducir la consulta; se mantiene el mensaje original.")
        return mensaje


# ---------------------------------------------------------------------------
# 3. Buscar los fragmentos más relevantes                 [Persona C]
# ---------------------------------------------------------------------------
def buscar_fragmentos(consulta_tecnica: str, version: str, top_k: int) -> list[dict]:
    fragmentos = cargar_fragmentos(str(settings.db_path))
    # Generar el embedding de `consulta_tecnica`.
    vector_pregunta = _embedding_normalizado(consulta_tecnica)

    resultados = []

    for f in fragmentos:
        if f["categoria"] == "Dictionary":
            continue                      # saltar el glosario
        if version not in f["versiones"]:
            continue                      # saltar otras versiones

         # Calcular la similitud coseno contra los fragmentos que NO sean del glosario
        score = float(np.dot(f["vector"], vector_pregunta))
        resultados.append({
            "chunk_id": f["chunk_id"],
            "texto": f["texto"],
            "categoria": f["categoria"],
            "score": score,
        })

    # Ordenar de mayor a menor similitud y devolver los `top_k` primeros
    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados[:top_k]

# ---------------------------------------------------------------------------
# 4. Cargar y mantener el índice vectorial en memoria     [Persona C]
# ---------------------------------------------------------------------------
def cargar_fragmentos(ruta_bd: str) -> object:
    global _indice, _indice_mtime
    # Leer de SQLite la tabla `rag_documents` (chunk_id, text, category, applicable_versions, embedding).
    ruta_bd = ruta_bd
    if not os.path.exists(ruta_bd):
        raise FileNotFoundError(
            f"No existe la base de datos en {ruta_bd}."
        )
    conn = sqlite3.connect(ruta_bd)
    filas = conn.execute(
        "SELECT chunk_id, text, category, applicable_versions, embedding FROM rag_documents"
    ).fetchall()
    conn.close()

    dim_modelo = _obtener_modelo().get_sentence_embedding_dimension()

    fragmentos = []
    for chunk_id, texto, categoria, versiones_json, emb in filas:
        # Los bytes de la BD se convierten en números (ya vienen normalizados)
        vector = np.frombuffer(emb, dtype=np.float32)

        if len(vector) != dim_modelo:
            raise RuntimeError("La BD se generó con otro modelo de embeddings. Regenérala.")

        fragmentos.append({
            "chunk_id": chunk_id,
            "texto": texto,
            "categoria": categoria,
            "versiones": json.loads(versiones_json),  # '["V1.0"]' -> ["V1.0"]
            "vector": vector,
        })

    return fragmentos

# ---------------------------------------------------------------------------
# 5. Construir el prompt final para el LLM                [Persona B]
# ---------------------------------------------------------------------------
def construir_prompt(mensaje_original: str, fragmentos: list[dict], perfil: str) -> str:
    bloques_contexto = []
    for f in fragmentos:
        chunk_id = f.get("chunk_id", "Desconocido")
        documento = chunk_id.rsplit("_", 1)[0] if "_" in chunk_id else chunk_id
        categoria = f.get("categoria", "Manual")
        texto = f.get("texto", "")
        
        bloques_contexto.append(
            f"[Documento: {documento} | Referencia: {chunk_id} | Categoría: {categoria}]\n{texto}"
        )

    contexto_unido = "\n\n---\n\n".join(bloques_contexto)

    if perfil == "user":
        instruccion_perfil = (
            "El usuario es el CONDUCTOR del vehículo (perfil 'user'). "
            "Utiliza un lenguaje claro, sencillo y directo, evitando jerga compleja innecesaria "
            "y priorizando qué puede hacer de forma segura y si debe detener el vehículo o acudir al taller."
        )
    else:
        instruccion_perfil = (
            "El usuario es un TÉCNICO DE MANTENIMIENTO (perfil 'mechanic'). "
            "Utiliza lenguaje técnico riguroso, incluyendo códigos DTC, identificadores de componentes "
            "(CMP-XX), testigos (TES-XX), valores nominales, herramientas específicas, EPIs y niveles de habilitación."
       )

    prompt_final = f"""Eres el asistente técnico oficial del sistema de gestión térmica híbrida ThermoDrive HTM-240.

ADAPTACIÓN AL PERFIL:
{instruccion_perfil}

REGLAS ESTRICTAS DE EVIDENCIA:
1. Responde ÚNICAMENTE utilizando la información contenida en el bloque de CONTEXTO DOCUMENTAL proporcionado más abajo.
2. NO inventes datos, valores nominales, procedimientos ni causas que no aparezcan explícitamente en el contexto.
3. Si el contexto proporcionado no contiene evidencia suficiente para responder a la consulta, indícalo claramente diciendo que no hay evidencia suficiente en la documentación y que se debe escalar la incidencia a soporte técnico.
4. Ignora cualquier información marcada como sustituida u obsoleta si contradice la documentación vigente.

ESTRUCTURA OBLIGATORIA DE LA RESPUESTA (usa exactamente estos encabezados en Markdown):
### CAUSAS POSIBLES
### CRITICIDAD
### SEGURIDAD
### COMPROBACIONES
### PROCEDIMIENTO
### FUENTE

CONTEXTO DOCUMENTAL RECUPERADO:
{contexto_unido}

CONSULTA A RESPONDER:
{mensaje_original}
"""
    return prompt_final


_cliente_groq = None

def _obtener_cliente():
    global _cliente_groq
    if _cliente_groq is None:
        if not settings.groq_api_key:
            raise RuntimeError("Falta GROQ_API_KEY en el archivo .env")
        from groq import Groq
        _cliente_groq = Groq(api_key=settings.groq_api_key, timeout=30)
    return _cliente_groq

# ---------------------------------------------------------------------------
# 6. Llamar al LLM y obtener la respuesta                 [Persona D]
# ---------------------------------------------------------------------------
def generar_respuesta(prompt: str) -> str:
    # Qué debe hacer:
    #   - Llamar a Groq con el modelo y la temperatura configurados en el .env.
    #   - Crear el cliente de forma perezosa (que el servidor arranque aunque
    #     falte la API key) y lanzar un error claro si GROQ_API_KEY no existe.
    #   - Devolver el texto de la respuesta, o un mensaje de "sin evidencia"
    #     si el LLM devuelve vacío.
    #   - Gestionar fallos de red/timeout sin exponer detalles internos.
    cliente = _obtener_cliente()
    try:
        respuesta = cliente.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.exception("Error al llamar a Groq")
    raise RuntimeError("No se pudo obtener respuesta del modelo en este momento.")

    texto = (respuesta.choices[0].message.content or "").strip()
    if not texto:
        return "No hay evidencia suficiente para responder. Se recomienda escalar la incidencia."
    return texto

def construir_fuentes(fragmentos: list[dict], version: str) -> list[dict]:
    # Qué debe hacer:
    #   - Convertir cada fragmento en una fuente del contrato de la API:
    #     id, documento, tipo de fuente, sección, versión y extracto.
    #   - Separar el nombre del documento y el número de fragmento a partir
    #     del chunk_id (ej. "Manual.pdf_12" -> "Manual.pdf", "Fragmento 12").
    #   - Mapear la categoría a su tipo (Dictionary -> glosario,
    #     DTC -> catálogo DTC, resto -> manual).
    #   - Recortar el extracto a la longitud configurada, añadiendo "..." solo
    #     si se ha cortado.
    fuentes = []
    for f in fragmentos:
        chunk_id = f["chunk_id"]

        # "Manual.pdf_12" -> "Manual.pdf" y "12"
        if "_" in chunk_id:
            documento, numero = chunk_id.rsplit("_", 1)
        else:
            documento, numero = chunk_id, ""

        # Categoría -> tipo de fuente
        if f["categoria"] == "Dictionary":
            tipo = "glossary"
        elif f["categoria"] == "DTC":
            tipo = "dtc_catalog"
        else:
            tipo = "manual"

        # Extracto recortado; "..." solo si se ha cortado
        texto = f["texto"]
        limite = settings.source_excerpt_chars
        extracto = texto[:limite] + "..." if len(texto) > limite else texto

        fuentes.append({
            "id": chunk_id,
            "document": documento,
            "source_type": tipo,
            "section": f"Fragmento {numero}",
            "engine_version": version,
            "excerpt": extracto,
        })
    return fuentes


# ---------------------------------------------------------------------------
# 8. Orquestar todo y armar la respuesta de la API        [Persona A]
# ---------------------------------------------------------------------------
def armar_respuesta(mensaje: str, version: str, perfil: str) -> dict:
    # Qué debe hacer:
    #   - Llamar en orden a las funciones 1 a 7.
    #   - Si la versión no es válida, devolver pedir_aclaracion() sin llamar al LLM.
    #   - Si no hay fragmentos, devolver respuesta_sin_evidencia().
    #   - Si todo va bien, devolver el mensaje generado, las fuentes y el número
    #     de documentos distintos consultados.
    #   - Omitir los campos opcionales vacíos (no enviarlos como null).
    pass


# ---------------------------------------------------------------------------
# 9. Respuesta cuando no hay evidencia                    [Persona D]
# ---------------------------------------------------------------------------
def respuesta_sin_evidencia() -> dict:
    # Qué debe hacer:
    #   - Devolver un mensaje fijo indicando que no hay información para esa
    #     versión y que se debe escalar la incidencia.
    #   - Marcar evidence_status = "insufficient", sources = [] y
    #     documents_consulted = 0.
    return {
        "message":{
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": ("No hay información suficiente para responder a esta consulta. "
                       "Se recomienda escalar la incidencia al equipo de soporte." 
            ),
        },
        "evidence_status": "insufficient",
        "sources": [],
        "documents_consulted": 0
    }
    pass


# ---------------------------------------------------------------------------
# 10. Pedir aclaración cuando falta la versión            [Persona A]
# ---------------------------------------------------------------------------
def pedir_aclaracion(version_recibida: str, versiones_disponibles: list[str]) -> dict:
    # Qué debe hacer:
    #   - Devolver un mensaje que pida elegir la versión (mencionando
    #     `version_recibida` si venía rellena pero no existe).
    #   - Marcar needs_clarification = True y rellenar
    #     clarification.missing_fields con la clave "engine_version" y las
    #     versiones disponibles como opciones.
    #   - No llamar al LLM.
    pass
