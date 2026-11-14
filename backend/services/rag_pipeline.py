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
            "coloquial añadiendo la terminología técnica oficial, códigos de componentes (CMP-XX), "
            "testigos (TES-XX) o DTC (HTM-XXXX) que aparezcan en el glosario adjunto.\n"
            "REGLA ESTRICTA: Conserva todos los códigos y datos originales de la pregunta y "
            "devuelve ÚNICAMENTE la consulta enriquecida en una sola frase, sin comillas ni explicaciones.\n\n"
            f"Glosario aplicable:\n{glosario_contexto}\n\n"
            f"Consulta original: {mensaje}\n\n"
            "Consulta técnica enriquecida:"
        )

        consulta_reescrita = generar_respuesta(prompt_traduccion).strip()

        if not consulta_reescrita or "No hay evidencia suficiente" in consulta_reescrita:
            return mensaje

        # Mantenemos el mensaje original + la traducción técnica para no perder palabras clave en la búsqueda
        return f"{mensaje} ({consulta_reescrita})"

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
def construir_prompt(
    mensaje_original: str,
    fragmentos: list[dict],
    perfil: str,
    historial: Optional[list[dict]] = None,
    version: Optional[str] = None,
) -> str:
    bloques_contexto = []
    for f in fragmentos:
        chunk_id = f.get("chunk_id", "Desconocido")
        documento = chunk_id.rsplit("_", 1)[0] if "_" in chunk_id else chunk_id
        categoria = f.get("categoria", "Manual")
        versiones = ", ".join(f.get("versiones", [])) if f.get("versiones") else "Todas"
        pagina = f.get("pagina")
        seccion = f.get("seccion")
        texto = f.get("texto", "")

        info_extra = []
        if seccion:
            info_extra.append(f"Sección: {seccion}")
        if pagina is not None:
            info_extra.append(f"Página: {pagina}")
        extra_str = " | " + " | ".join(info_extra) if info_extra else ""

        bloques_contexto.append(
            f"[Documento: {documento} | Fragmento: {chunk_id} | Categoría: {categoria} | Versiones aplicables: {versiones}{extra_str}]\n{texto}"
        )

    contexto_unido = "\n\n---\n\n".join(bloques_contexto)

    if perfil == "user":
        instruccion_perfil = (
            "El usuario es el CONDUCTOR del vehículo (perfil 'user'). "
            "Usa un lenguaje claro, accesible y directo. Prioriza su seguridad, qué NO debe tocar "
            "y si debe detener el vehículo de inmediato o acudir al taller."
        )
    else:
        instruccion_perfil = (
            "El usuario es un TÉCNICO DE MANTENIMIENTO (perfil 'mechanic'). "
            "Usa lenguaje técnico preciso: incluye códigos DTC (HTM-XXXX), componentes (CMP-XX), "
            "testigos (TES-XX), circuitos (CIR-01/02/03), herramientas (HTM-TOOL-XX), EPIs y niveles de habilitación."
        )

    bloque_historial = (
        f"\nHISTORIAL RECIENTE DE LA CONVERSACIÓN:\n{_formatear_historial(historial)}\n"
        if historial
        else ""
    )
    version_seleccionada = version or "No especificada"

    prompt_final = f"""Eres el asistente técnico oficial del sistema de gestión térmica híbrida ThermoDrive HTM-240.

ADAPTACIÓN AL PERFIL:
{instruccion_perfil}

VERSIÓN SELECCIONADA EN LA INTERFAZ: {version_seleccionada}
{bloque_historial}
REGLAS CRÍTICAS DE PRECISIÓN, VERSIONES Y OBSOLESCENCIA (OBLIGATORIAS):
1. FIDELIDAD Y CERO CÓDIGOS INVENTADOS: Responde SOLO con los datos del CONTEXTO DOCUMENTAL. Está TERMINANTEMENTE PROHIBIDO inventar datos, pares de apriete, resistencias o escribir referencias ficticias con signos de interrogación como "HTM240-PRC-??". Cita siempre el código real del documento, sección y página (ej. HTM240-CAT-001, HTM240-DIA-001, HTM240-BOL-006). Si no hay datos para responder, incluye exactamente la frase "No hay evidencia suficiente en la documentación".
2. DATOS OBSOLETOS Y JERARQUÍA DOCUMENTAL (Boletín > Manual vigente > Manual obsoleto):
   - Da siempre como respuesta principal el dato VIGENTE indicando en qué documento y versión se aplica.
   - ADICIONALMENTE, si en el contexto aparece un valor anterior u obsoleto o un boletín que corrige un documento (ej. HTM240-BOL-006 corrige los 80.000 km / 60 meses de HTM240-MNT-001 v1.0 a 60.000 km / 48 meses en v1.1; o HTM240-BOL-002 actualiza PRC-003 a v2.0), DEBES MENCIONAR EXPRESAMENTE qué dato está obsoleto, a qué versión antigua pertenecía y qué boletín/versión contiene el dato correcto vigente.
3. LECTURA MULTIVERSIÓN (V1.0, V1.1 y V2.0):
   - Aunque en la interfaz figure seleccionada la versión {version_seleccionada}, si el usuario NO especifica la versión en el texto de su pregunta y el dato o código consultado varía entre versiones (ej. corriente nominal de la bomba CMP-02: 3-5 A en V1.0 vs. 3-6 A en V1.1/V2.0 según HTM240-BOL-002; o el código HTM-0142: precalentamiento no completado en V1.x vs. fallo del sensor combinado CMP-18 en V2.0 según HTM240-BOL-003; o potencia del PTC CMP-12 en BOL-007), EXPÓN LOS DATOS DE TODAS LAS VERSIONES indicando cuál corresponde a cada una y pide confirmar la versión real del vehículo antes de sustituir piezas.
4. AMBIGÜEDAD DE COMPONENTES (PROHIBIDO ASUMIR):
   - Si preguntan por "la bomba" sin especificar cuál, NO asumas CMP-02: pide aclaración indicando que existen tres bombas: CMP-01 (mecánica, CIR-01 motor), CMP-02 (eléctrica auxiliar A, CIR-02 batería) y CMP-03 (eléctrica auxiliar B, CIR-03 electrónica de potencia).
   - Si preguntan por "el radiador" sin especificar cuál, pide aclaración indicando que existen dos radiadores: CMP-05 (radiador principal, CIR-01) y CMP-06 (radiador auxiliar de baja temperatura, CIR-02/CIR-03).
5. SEGURIDAD CRÍTICA Y AVISO DE USO EDUCATIVO:
   - COCHE REAL: Si el usuario menciona reparar un "coche real" o vehículo real, advierte EN PRIMER LUGAR que toda la documentación ThermoDrive HTM-240 es SINTÉTICA Y FICTICIA PARA USO EXCLUSIVAMENTE EDUCATIVO y que jamás debe usarse para reparar un vehículo real (remite a los manuales oficiales del fabricante).
   - RIESGO ELÉCTRICO / TÉRMICO: Ante testigo rojo de alta tensión (TES-05), olor a quemado, humo, modo tortuga con alerta roja o fugas en componentes de batería/alta tensión (CMP-10, CMP-12, CIR-02, CIR-03), NUNCA escribas "SEGURIDAD: No consta". Ordena SIEMPRE en primer lugar: detención inmediata y segura del vehículo, apagar contacto, NO manipular manguitos ni alta tensión (300-400V), verificar desconexión eléctrica, esperar a temperatura < 40 °C para no sufrir quemaduras por proyección de fluido (HTM240-SEG-001) y escalar a Técnico Nivel 3 habilitado en alta tensión.
6. FUERA DE ALCANCE vs. LÍMITE DE INFORMACIÓN:
   - Si preguntan por subsistemas ajenos (frenos, aceite de caja de cambios, compresor o gas del aire acondicionado del habitáculo), declara explícitamente que "No hay evidencia suficiente en la documentación" porque queda FUERA DEL ALCANCE del sistema ThermoDrive HTM-240, el cual solo cubre los tres circuitos térmicos (motor CIR-01, batería CIR-02 y electrónica de potencia CIR-03).
   - Si preguntan por un dato no documentado de un componente que sí existe (ej. par de apriete en Nm de la TCU CMP-13 o curva de resistencia en ohmios de CMP-14 a 20 °C), identifica primero el componente según el catálogo (HTM240-CAT-001) y aclara que "No hay evidencia suficiente en la documentación" porque el corpus no incluye tablas de pares de apriete ni curvas de resistencia eléctrica, recomendando escalar a soporte.

PROPORCIONALIDAD Y ESTRUCTURA DE SALIDA:
- En consultas de diagnóstico, averías, testigos, códigos DTC o procedimientos, utiliza estos encabezados en Markdown:
### CAUSAS POSIBLES
### CRITICIDAD
### SEGURIDAD
### COMPROBACIONES
### PROCEDIMIENTO
### FUENTE
- En consultas directas simples (ej. preguntar solo qué función tiene un componente, qué herramienta usa un paso o cada cuántos km se cambia el fluido) o consultas fuera de alcance/ambiguas, responde de forma directa, completa y concisa a lo preguntado citando la `### FUENTE` (y `### SEGURIDAD` si aplica), SIN inventar pasos de desmontaje que nadie ha pedido ni rellenar secciones vacías con "No consta en la documentación recuperada".

CONTEXTO DOCUMENTAL RECUPERADO:
{contexto_unido}

CONSULTA DEL USUARIO:
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
