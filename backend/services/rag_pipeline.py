"""
Proceso de consulta RAG de ThermoDrive.

Recibe la pregunta del usuario, busca en la documentación técnica los fragmentos
más relevantes para su versión del motor y pide al LLM una respuesta basada
solo en esos fragmentos. Lo usa el endpoint POST /api/chat
(controllers/chat_controller.py llama a `armar_respuesta`).

Autores (reparto del equipo):
  Fabián  (Persona A, integrador)        -> 1. validar_consulta, 8. armar_respuesta, 10. pedir_aclaracion
  Samair  (Persona B, prompts)           -> 2. traducir_consulta, 5. construir_prompt
  Jorge   (Persona C, búsqueda vectorial) -> 3. buscar_fragmentos, 4. cargar_fragmentos
  Miguel  (Persona D, LLM y salida)      -> 6. generar_respuesta, 7. construir_fuentes, 9. respuesta_sin_evidencia

Flujo de una consulta:

  pregunta + versión
      -> 1. validar_consulta         limpia el mensaje y comprueba la versión
      -> 2. traducir_consulta        pasa el lenguaje coloquial a términos técnicos
      -> 3. buscar_fragmentos        busca los fragmentos más parecidos (usa 4. cargar_fragmentos)
      -> 5. construir_prompt         junta reglas + fragmentos + pregunta
      -> 6. generar_respuesta        llama al LLM (Groq)
      -> 7. construir_fuentes        prepara las fuentes para el frontend
      -> 8. armar_respuesta          orquesta todo (usa 9. respuesta_sin_evidencia / 10. pedir_aclaracion)

Configuración (backend/config.py -> `from config import settings`, valores en el .env):
  settings.db_path, settings.embedding_model, settings.groq_api_key,
  settings.llm_model, settings.llm_temperature, settings.rag_top_k,
  settings.rag_dictionary_top_k, settings.rag_dictionary_min_score,
  settings.rag_evidence_min_score, settings.rag_evidence_high_score,
  settings.source_excerpt_chars
Modelos del contrato de la API: models/schemas.py (ChatResponse, Source, ...).
"""

from typing import Literal, Optional, cast
from sentence_transformers import SentenceTransformer
import logging
import uuid

from config import settings

import json
import os
import re
import sqlite3
import numpy as np

logger = logging.getLogger(__name__)

# Modelo de embeddings ya cargado (se rellena la primera vez que se usa).
_modelo_embeddings = None

# Versiones del motor admitidas.                                  [Fabián]
# Provisional: están fijas aquí, todavía no se leen de la base de datos.
VERSIONES_CONOCIDAS = ["V1.0", "V1.1", "V2.0"]


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES                                              [Jorge]
# Las usan buscar_fragmentos (Jorge) y traducir_consulta (Samair).
# ---------------------------------------------------------------------------

def _obtener_modelo():
    """Devuelve el modelo de embeddings, cargándolo solo la primera vez.

    Cargar el modelo tarda varios segundos, por eso se guarda en una variable
    global y las siguientes llamadas reutilizan el mismo.
    """
    global _modelo_embeddings

    if _modelo_embeddings is None:
        _modelo_embeddings = SentenceTransformer(settings.embedding_model)

    return _modelo_embeddings


def _embedding_normalizado(texto: str) -> np.ndarray:
    """Convierte un texto en un vector de longitud 1.

    Los vectores de la BD también están normalizados (el generador usa
    normalize_embeddings=True), así que el producto escalar entre ambos es
    directamente la similitud coseno (de -1 a 1).
    """
    vector = _obtener_modelo().encode(texto, convert_to_numpy=True, show_progress_bar=False)
    vector = vector.astype(np.float32)
    # Dividir entre su longitud; el "or 1.0" evita dividir entre 0.
    return vector / (np.linalg.norm(vector) or 1.0)

def _formatear_historial(historial: list[dict], max_chars: int = 500) -> str:
    """Convierte el historial en texto para meterlo en un prompt.

    Las respuestas del asistente son largas (6 secciones), así que se recortan
    para no inflar el prompt.
    """
    lineas = []
    for h in historial:
        quien = "Usuario" if h["role"] == "user" else "Asistente"
        texto = h["content"].strip()
        if len(texto) > max_chars:
            texto = texto[:max_chars] + "..."
        lineas.append(f"{quien}: {texto}")
    return "\n".join(lineas)


def reformular_con_historial(mensaje: str, historial: list[dict]) -> str:
    """Convierte una pregunta de seguimiento en una que se entienda sin el chat.

    "¿y cómo lo compruebo?" -> "¿cómo se comprueba el electroventilador que no arranca?"
    Si algo falla, devuelve el mensaje original.
    """
    if not historial:
        return mensaje   # primera pregunta del chat: no hay nada que reformular

    prompt = (
        "Dada la conversación anterior y la nueva pregunta, reescribe la nueva pregunta "
        "para que se entienda sin la conversación (sustituye 'eso', 'lo', 'y si...' por "
        "lo que corresponda). Si ya se entiende sola, devuélvela igual.\n"
        "Devuelve ÚNICAMENTE la pregunta reescrita.\n\n"
        f"Conversación:\n{_formatear_historial(historial)}\n\n"
        f"Nueva pregunta: {mensaje}\n\n"
        "Pregunta reescrita:"
    )
    try:
        reescrita = generar_respuesta(prompt).strip()
        return reescrita or mensaje
    except Exception:
        logger.warning("No se pudo reformular con el historial; se usa el mensaje original.")
        return mensaje


# ---------------------------------------------------------------------------
# 1. Validar la consulta y la versión del motor                     [Fabián]
# ---------------------------------------------------------------------------
def validar_consulta(mensaje: str, version: str, versiones_conocidas: list[str]) -> tuple[str, Optional[str]]:
    """Limpia el mensaje y busca la versión entre las conocidas.

    Devuelve (mensaje_limpio, version_canonica). Si la versión está vacía o no
    existe, version_canonica es None y armar_respuesta pedirá aclaración.
    """
    mensaje_limpio = mensaje.strip()

    if not mensaje_limpio:
        raise ValueError("El mensaje no puede estar vacío")

    # Comparar sin espacios ni mayúsculas: " v2.0 " -> "V2.0".
    version_limpia = "".join(version.split()).upper()

    for conocida in versiones_conocidas:
        if version_limpia == "".join(conocida.split()).upper():
            # Se devuelve la versión tal como está escrita en la lista.
            return mensaje_limpio, conocida

    return mensaje_limpio, None


# ---------------------------------------------------------------------------
# 2. Traducir la consulta coloquial a lenguaje técnico              [Samair]
# ---------------------------------------------------------------------------
def traducir_consulta(mensaje: str) -> str:
    """Reescribe la pregunta con la terminología del glosario técnico.

    Ejemplo: "el ventilador no va" -> "fallo del electroventilador CMP-09".
    Así la búsqueda encuentra mejor los fragmentos de los manuales. Es una fase
    opcional: si no hay términos relevantes o algo falla, se devuelve el
    mensaje original.
    """
    try:
        fragmentos = cargar_fragmentos(str(settings.db_path))
        vector_mensaje = _embedding_normalizado(mensaje)

        # Buscar en el glosario (categoría "Dictionary") los términos parecidos
        # a la pregunta que superen la puntuación mínima.
        terminos_relevantes = []
        for f in fragmentos:
            if f["categoria"] != "Dictionary":
                continue

            score = float(np.dot(f["vector"], vector_mensaje))
            if score >= settings.rag_dictionary_min_score:
                terminos_relevantes.append((score, f["texto"]))

        if not terminos_relevantes:
            return mensaje

        # Quedarse con los top-k términos más parecidos.
        terminos_relevantes.sort(key=lambda x: x[0], reverse=True)
        mejores_terminos = [
            texto for _, texto in terminos_relevantes[:settings.rag_dictionary_top_k]
        ]

        glosario_contexto = "\n".join(f"- {t}" for t in mejores_terminos)

        # Pedir al LLM que reescriba la pregunta usando esos términos.
        prompt_traduccion = (
            "Eres un asistente técnico de automoción. Reescribe la siguiente consulta "
            "coloquial utilizando la terminología técnica oficial del glosario adjunto.\n"
            "Regla estricta: devuelve ÚNICAMENTE la consulta reescrita en una sola frase, "
            "sin introducciones, sin comillas y sin explicaciones adicionales.\n"
            "No añadas síntomas, causas ni comprobaciones que no estén en la consulta original: "
            "solo cambia las palabras coloquiales por su término técnico. Conserva tal cual los "
            "códigos de avería (HTM-XXXX), las versiones (V1.0, V2.0...) y los identificadores "
            "(CMP-XX, TES-XX).\n\n"
            f"Glosario aplicable:\n{glosario_contexto}\n\n"
            f"Consulta original: {mensaje}\n\n"
            "Consulta reescrita:"
        )

        consulta_reescrita = generar_respuesta(prompt_traduccion).strip()

        # Si el LLM no devuelve nada útil, seguir con la pregunta original.
        if not consulta_reescrita or "No hay evidencia suficiente" in consulta_reescrita:
            return mensaje

        return consulta_reescrita

    except Exception:
        logger.warning("Fallo al traducir la consulta; se mantiene el mensaje original.")
        return mensaje


# ---------------------------------------------------------------------------
# 3. Buscar los fragmentos más relevantes                            [Jorge]
# ---------------------------------------------------------------------------
def _normalizar_guiones(texto: str) -> str:
    """Unifica los guiones raros que salen de los PDF o del LLM ("HTM‑0142" -> "HTM-0142")."""
    return re.sub(r"[‐-―−]", "-", texto)


def buscar_fragmentos(consulta_tecnica: str, version: str, top_k: int) -> list[dict]:
    """Devuelve los top_k fragmentos más parecidos a la consulta para esa versión.

    Cada resultado es {"chunk_id", "texto", "categoria", "score", "versiones",
    "pagina", "seccion"}, ordenados de mayor a menor score. Lista vacía si no hay ninguno.
    """
    fragmentos = cargar_fragmentos(str(settings.db_path))
    vector_pregunta = _embedding_normalizado(consulta_tecnica)

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


# ---------------------------------------------------------------------------
# 4. Cargar los fragmentos de la base de datos                       [Jorge]
# ---------------------------------------------------------------------------
def cargar_fragmentos(ruta_bd: str) -> list[dict]:
    """Lee todos los fragmentos de la tabla rag_documents.

    Se lee la BD en cada llamada (sin caché), así que si se regenera se usa
    siempre la versión actual sin reiniciar el servidor.
    Devuelve una lista de dicts: {"chunk_id", "texto", "categoria", "versiones",
    "vector", "pagina", "seccion"}. "pagina" es la página del PDF donde empieza el
    fragmento y "seccion" el código del caso de servicio (None si no aplica).
    """
    if not os.path.exists(ruta_bd):
        raise FileNotFoundError(
            f"No existe la base de datos en {ruta_bd}."
        )
    conn = sqlite3.connect(ruta_bd)
    try:
        filas = conn.execute(
            "SELECT chunk_id, text, category, applicable_versions, embedding, page, section "
            "FROM rag_documents"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # BD generada con una versión anterior del generador (sin page/section).
        raise RuntimeError(
            "La BD es de una versión anterior. Regénerala con backend/db/database_generator.py"
        ) from exc
    finally:
        conn.close()

    # Tamaño de los vectores que genera el modelo configurado (384 en el actual).
    # El método se renombró en sentence-transformers 6: se usa el que exista
    # para que funcione con cualquier versión instalada.
    modelo = _obtener_modelo()
    obtener_dimension = getattr(modelo, "get_embedding_dimension", None) or modelo.get_sentence_embedding_dimension
    dim_modelo = obtener_dimension()

    fragmentos = []
    for chunk_id, texto, categoria, versiones_json, emb, pagina, seccion in filas:
        # En SQLite el embedding está guardado como bytes: se convierten a números.
        # Ya vienen normalizados desde el generador.
        vector = np.frombuffer(emb, dtype=np.float32)

        # Si la BD se generó con otro modelo, los vectores no son comparables.
        if len(vector) != dim_modelo:
            raise RuntimeError("La BD se generó con otro modelo de embeddings. Regenérala.")

        fragmentos.append({
            "chunk_id": chunk_id,
            "texto": texto,
            "categoria": categoria,
            # SQLite no guarda listas: viene como texto JSON '["V1.0"]' -> ["V1.0"].
            "versiones": json.loads(versiones_json),
            "vector": vector,
            "pagina": pagina,
            "seccion": seccion,
        })

    return fragmentos


# ---------------------------------------------------------------------------
# 5. Construir el prompt final para el LLM                          [Samair]
# ---------------------------------------------------------------------------
def construir_prompt(mensaje_original: str, fragmentos: list[dict], perfil: str, historial: list[dict],
                     version: str) -> str:
    """Junta las reglas, los fragmentos recuperados, la conversación previa y la pregunta en un solo prompt.

    `perfil` adapta el estilo: "mechanic" (técnico) o "user" (conductor, sencillo).
    `historial` son los últimos mensajes del chat; sirve para que el LLM entienda
    preguntas de seguimiento ("¿y cómo lo compruebo?"), pero NO es fuente de evidencia.
    """
    # Un bloque por fragmento, indicando de qué documento sale.
    bloques_contexto = []
    for f in fragmentos:
        chunk_id = f.get("chunk_id", "Desconocido")
        documento = chunk_id.rsplit("_", 1)[0] if "_" in chunk_id else chunk_id
        categoria = f.get("categoria", "Manual")
        texto = f.get("texto", "")
        # Página y caso, si los hay, para que el LLM pueda citarlos en el texto.
        pagina = f" | Página: {f['pagina']}" if f.get("pagina") else ""
        seccion = f" | Caso: {f['seccion']}" if f.get("seccion") else ""

        bloques_contexto.append(
            f"[Documento: {documento}{pagina}{seccion} | Categoría: {categoria}]\n{texto}"
        )

    contexto_unido = "\n\n---\n\n".join(bloques_contexto)

    # Instrucciones de estilo según quién pregunta.
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

    # Conversación previa: solo para entender a qué se refiere el usuario.
    # Si es la primera pregunta del chat, el bloque queda vacío y no aparece en el prompt.
    bloque_historial = ""
    if historial:
        bloque_historial = (
            "CONVERSACIÓN PREVIA (solo para entender a qué se refiere el usuario; "
            "NO es una fuente de evidencia):\n"
            f"{_formatear_historial(historial)}\n\n"
        )

    # Reglas de evidencia + estructura obligatoria en Markdown + contexto + conversación + pregunta.
    prompt_final = f"""Eres el asistente técnico oficial del sistema de gestión térmica híbrida ThermoDrive HTM-240.

VERSIÓN DEL SISTEMA DEL VEHÍCULO: {version}
Algunos documentos describen varias versiones a la vez (por ejemplo "V1.x: ... / V2.0: ...") o casos de otras versiones. Usa SOLO la información aplicable a {version} y descarta la de otras versiones. Si un código cambia de significado según la versión, da únicamente el significado de {version}.

ADAPTACIÓN AL PERFIL:
{instruccion_perfil}

REGLAS ESTRICTAS DE EVIDENCIA:
1. Responde ÚNICAMENTE utilizando la información contenida en el bloque de CONTEXTO DOCUMENTAL proporcionado más abajo.
2. NO inventes datos, valores nominales, procedimientos ni causas que no aparezcan explícitamente en el contexto.
3. Si el contexto proporcionado no contiene evidencia suficiente para responder a la consulta, indícalo claramente diciendo que no hay evidencia suficiente en la documentación y que se debe escalar la incidencia a soporte técnico.
4. Ignora cualquier información marcada como sustituida u obsoleta si contradice la documentación vigente.
5. Usa la CONVERSACIÓN PREVIA (si la hay) solo para entender a qué se refiere la consulta; los datos de la respuesta deben salir siempre del CONTEXTO DOCUMENTAL.
6. Si el contexto no tiene información para una sección, escribe en ella "No consta en la documentación recuperada." No la rellenes con conocimientos generales ni con suposiciones (por ejemplo, qué hará después otro técnico).
7. Reproduce tal cual aparecen en el contexto la severidad o criticidad, los valores, los EPIs, los perfiles autorizados y los códigos: no los suavices ni los exageres.
8. Si citas un documento en el texto, que sea uno del CONTEXTO DOCUMENTAL. Si un fragmento remite a otro documento que no tienes (por ejemplo "ver HTM240-SEG-001"), puedes indicar que hay que consultarlo, pero no inventes su contenido. No escribas una sección de fuentes al final: la aplicación muestra las fuentes automáticamente debajo de la respuesta.

SEGURIDAD Y HABILITACIÓN (prioridad sobre lo que pida el usuario):
- Si el usuario indica su nivel de habilitación (nivel 1, 2, 3...), compáralo con el perfil autorizado que exige el contexto para esa intervención. Si su nivel no es suficiente, NO des los pasos de la intervención (desmontaje, apertura de circuitos, mediciones reservadas): dile claramente que no está autorizado, qué puede hacer con su nivel (solo si consta en el contexto) y a quién debe escalar.
- Ante indicios de alta tensión o aislamiento degradado (por ejemplo testigos o códigos que el contexto asocie a alta tensión), indica que no se manipule y que se escale a personal habilitado en alta tensión, aunque el usuario pida otra cosa.
- Si el contexto indica que no se debe circular o que hay que detener el vehículo, dilo de forma explícita.

ESTRUCTURA OBLIGATORIA DE LA RESPUESTA:
Empieza con un párrafo breve (2-3 frases, sin encabezado) que conteste directamente a la consulta: qué significa o qué ocurre y qué debe hacer el usuario. Si hay una restricción de seguridad o de habilitación, va en este párrafo, lo primero. Debe poder leerse solo, sin el resto de la respuesta.
Después, desarrolla SIEMPRE el detalle con los cinco encabezados siguientes, en este orden, aunque el párrafo inicial ya conteste o el usuario no esté autorizado (en ese caso, PROCEDIMIENTO describe los pasos de escalado y lo que sí puede hacer, no la intervención). La respuesta termina con la sección PROCEDIMIENTO, sin nada después:
### CAUSAS POSIBLES
### CRITICIDAD
### SEGURIDAD
### COMPROBACIONES
### PROCEDIMIENTO

CONTEXTO DOCUMENTAL RECUPERADO:
{contexto_unido}

{bloque_historial}CONSULTA A RESPONDER:
{mensaje_original}
"""
    return prompt_final


# Cliente de Groq ya creado (se rellena la primera vez que se usa).  [Miguel]
_cliente_groq = None

# Valores que admite Groq para `reasoning_effort` (LLM_REASONING_EFFORT en el .env).
EsfuerzoRazonamiento = Literal["none", "default", "low", "medium", "high"]

def _obtener_cliente():
    """Crea el cliente de Groq solo cuando hace falta.

    Así el servidor arranca aunque falte la API key; el error salta al hacer
    la primera consulta.
    """
    global _cliente_groq
    if _cliente_groq is None:
        if not settings.groq_api_key:
            raise RuntimeError("Falta GROQ_API_KEY en el archivo .env")
        from groq import Groq
        _cliente_groq = Groq(api_key=settings.groq_api_key, timeout=30)
    return _cliente_groq


# ---------------------------------------------------------------------------
# 6. Llamar al LLM y obtener la respuesta                           [Miguel]
# ---------------------------------------------------------------------------
def generar_respuesta(prompt: str) -> str:
    """Envía el prompt a Groq y devuelve el texto de la respuesta.

    Usa el modelo y la temperatura del .env. Si Groq falla (red, timeout...)
    se registra el detalle en el log y se lanza un error genérico, sin exponer
    información interna al usuario.
    """
    from groq import omit

    cliente = _obtener_cliente()

    # Esfuerzo de razonamiento: solo para modelos que razonan (gpt-oss). Si en el
    # .env está vacío, `omit` hace que no se envíe el parámetro.
    esfuerzo = (
        cast(EsfuerzoRazonamiento, settings.llm_reasoning_effort)
        if settings.llm_reasoning_effort
        else omit
    )
    try:
        respuesta = cliente.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[{"role": "user", "content": prompt}],
            # gpt-oss razona antes de contestar y ese razonamiento gasta tokens del
            # mismo límite que la respuesta: con poco margen sale cortada o vacía.
            max_completion_tokens=settings.llm_max_tokens,
            reasoning_effort=esfuerzo,
        )
    except Exception:
        logger.exception("Error al llamar a Groq")
        raise RuntimeError("No se pudo obtener respuesta del modelo en este momento.")

    texto = (respuesta.choices[0].message.content or "").strip()
    # Si el LLM devuelve vacío, se responde como "sin evidencia".
    if not texto:
        return "No hay evidencia suficiente para responder. Se recomienda escalar la incidencia."
    return texto


# ---------------------------------------------------------------------------
# 7. Construir las fuentes para el contrato de la API               [Miguel]
# ---------------------------------------------------------------------------
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


def construir_fuentes(fragmentos: list[dict], version: str) -> list[dict]:
    """Convierte cada fragmento en una fuente con el formato de `Source` (schemas.py)."""
    fuentes = []
    for f in fragmentos:
        chunk_id = f["chunk_id"]

        # "Manual.pdf_12" -> documento "Manual.pdf".
        documento = chunk_id.rsplit("_", 1)[0] if "_" in chunk_id else chunk_id

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
        })
    return fuentes


# ---------------------------------------------------------------------------
# 8. Orquestar todo y armar la respuesta de la API                  [Fabián]
# ---------------------------------------------------------------------------
def armar_respuesta(mensaje: str, version: str, perfil: str, historial: list[dict]) -> dict:
    """Ejecuta el flujo completo y devuelve un dict con el formato de ChatResponse.

    `historial` son los últimos mensajes del chat ([{"role", "content"}, ...]),
    tal como llegan del frontend.
    """
    # 1. Validar mensaje y versión.
    mensaje_limpio, version_canonica = validar_consulta(
        mensaje,
        version,
        VERSIONES_CONOCIDAS,
    )

    # Versión vacía o desconocida: pedir que la elija, sin llamar al LLM.
    if version_canonica is None:
        return pedir_aclaracion(version, VERSIONES_CONOCIDAS)

    # 2. Reformular con el historial (para preguntas de seguimiento) y pasar
    #    la pregunta a lenguaje técnico. Ambas versiones solo sirven para buscar.
    pregunta_autonoma = reformular_con_historial(mensaje_limpio, historial)
    consulta_tecnica = traducir_consulta(pregunta_autonoma)

    # 3. Buscar los fragmentos más relevantes de esa versión.
    fragmentos = buscar_fragmentos(
        consulta_tecnica,
        version_canonica,
        settings.rag_top_k,
    )

    # Nivel de evidencia según la similitud del mejor fragmento.     [Jorge]
    # Si ninguno se parece lo suficiente (o no hay), no se llama al LLM.
    mejor_score = fragmentos[0]["score"] if fragmentos else 0.0
    if mejor_score < settings.rag_evidence_min_score:
        return respuesta_sin_evidencia()

    # 5. Construir el prompt. Se usa el mensaje original del usuario, no la
    #    versión traducida (esa solo sirve para buscar).
    prompt_final = construir_prompt(
        mensaje_limpio,
        fragmentos,
        perfil,
        historial,
        version_canonica,
    )

    # 6. Obtener la respuesta del LLM.
    texto_respuesta = generar_respuesta(prompt_final)

    # evidence_status: insuficiente si el propio LLM dice que no hay      [Jorge]
    # evidencia; si no, alta o media según el mejor score.
    if "no hay evidencia suficiente" in texto_respuesta.lower():
        evidencia = "insufficient"
    elif mejor_score >= settings.rag_evidence_high_score:
        evidencia = "high"
    else:
        evidencia = "medium"

    # 7. Preparar las fuentes y contar los documentos distintos usados.
    fuentes = construir_fuentes(fragmentos, version_canonica)

    documentos = {fuente["document"] for fuente in fuentes}

    return {
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": texto_respuesta,
        },
        "evidence_status": evidencia,
        "sources": fuentes,
        "documents_consulted": len(documentos),
        "needs_clarification": False,
    }


# ---------------------------------------------------------------------------
# 9. Respuesta cuando no hay evidencia                              [Miguel]
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 10. Pedir aclaración cuando falta la versión                      [Fabián]
# ---------------------------------------------------------------------------
def pedir_aclaracion(version_recibida: str, versiones_disponibles: list[str]) -> dict:
    """Pide al usuario que elija la versión del motor. No llama al LLM.

    El frontend usa `clarification.missing_fields` para mostrar un selector
    con las versiones disponibles.
    """
    version_recibida = version_recibida.strip()
    opciones = ", ".join(versiones_disponibles)

    # Mensaje distinto si la versión venía rellena pero no existe, o si venía vacía.
    if version_recibida:
        texto = (
            f"La versión «{version_recibida}» no está reconocida. "
            f"Selecciona una de estas versiones: {opciones}."
        )
    else:
        texto = (
            "¿Qué versión tiene tu vehículo? "
            f"Selecciona una de estas versiones: {opciones}."
        )

    return {
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": texto,
        },
        "needs_clarification": True,
        "clarification": {
            "message": texto,
            "missing_fields": [
                {
                    "key": "engine_version",
                    "label": "Versión del motor",
                    "options": versiones_disponibles,
                }
            ],
        },
        "sources": [],
        "documents_consulted": 0,
    }
