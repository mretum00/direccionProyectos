"""
Todo lo que se le pide al LLM (Groq).

- generar_respuesta: envía un prompt a Groq y devuelve el texto de la respuesta.
  Crea el cliente solo la primera vez.
- reformular_con_historial: convierte una pregunta de seguimiento
  ("¿y cómo lo compruebo?") en una que se entienda sin el chat.
- traducir_consulta: pasa el lenguaje coloquial a términos técnicos usando el
  glosario de la BD, para buscar mejor.
"""

import logging
from typing import Literal, cast

import numpy as np

from config import settings

from .embeddings import embedding_normalizado
from .prompts import formatear_historial
from .retrieval import cargar_fragmentos

logger = logging.getLogger(__name__)


# Cliente de Groq ya creado (se rellena la primera vez que se usa).
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
        f"Conversación:\n{formatear_historial(historial)}\n\n"
        f"Nueva pregunta: {mensaje}\n\n"
        "Pregunta reescrita:"
    )
    try:
        reescrita = generar_respuesta(prompt).strip()
        return reescrita or mensaje
    except Exception:
        logger.warning("No se pudo reformular con el historial; se usa el mensaje original.")
        return mensaje


def traducir_consulta(mensaje: str) -> str:
    """Añade a la consulta la terminología técnica que aparezca en el glosario.

    Busca en el glosario (categoría "Dictionary") los términos parecidos a la
    pregunta y le pide al LLM que la reescriba con ellos (códigos CMP, TES, HTM).
    Devuelve "mensaje (consulta enriquecida)"; si algo falla, el mensaje original.
    Solo sirve para buscar: el prompt final usa la pregunta original.
    """
    try:
        fragmentos = cargar_fragmentos()
        vector_mensaje = embedding_normalizado(mensaje)

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