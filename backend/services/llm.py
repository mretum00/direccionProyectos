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
import re
import time
from typing import Literal, cast

import numpy as np

from config import settings

from .embeddings import embedding_normalizado
from .prompts import formatear_historial
from .retrieval import cargar_fragmentos
from .texto import limpiar_salida_llm

logger = logging.getLogger(__name__)


# Cliente de Groq ya creado (se rellena la primera vez que se usa).
_cliente_groq = None

# Valores que admite Groq para `reasoning_effort` (LLM_REASONING_EFFORT en el .env).
EsfuerzoRazonamiento = Literal["low", "medium", "high"]


def _obtener_cliente():
    """Crea el cliente de Groq solo cuando hace falta.

    El SDK aplica hasta dos reintentos automáticos a errores transitorios; el timeout
    limita cuánto puede quedar bloqueada una consulta.
    """
    global _cliente_groq
    if _cliente_groq is None:
        if not settings.groq_api_key:
            from .errores_llm import LLMServiceError

            raise LLMServiceError(
                "missing_api_key",
                "El servicio de IA no está configurado. Contacta con el administrador.",
            )
        from groq import Groq
        _cliente_groq = Groq(
            api_key=settings.groq_api_key,
            timeout=30,
            max_retries=2,
        )
    return _cliente_groq


def _llamar_groq(
    prompt: str,
    *,
    verificacion: bool = False,
    max_completion_tokens_override: int | None = None,
    reasoning_effort_override: str | None = None,
    json: bool = False,
) -> str:
    """Realiza una llamada a Groq y traduce sus errores a LLMServiceError.

    Para verificaciones estructuradas se puede reducir el presupuesto de salida y
    usar el nivel mínimo de razonamiento admitido por Groq (low). Si Groq devuelve un 429 con una espera
    transitoria explícita inferior a 1,5 s, se hace un único reintento acotado.
    Con `json=True` se activa el modo JSON de Groq: la salida siempre es JSON válido
    (sin él, una comilla sin escapar en una cita rompía la verificación y R07).
    """
    from .errores_llm import LLMServiceError, clasificar_error_groq

    try:
        from groq import omit

        cliente = _obtener_cliente()
        if reasoning_effort_override is not None:
            esfuerzo = cast(EsfuerzoRazonamiento, reasoning_effort_override)
        else:
            esfuerzo = (
                cast(EsfuerzoRazonamiento, settings.llm_reasoning_effort)
                if settings.llm_reasoning_effort
                else omit
            )
        limite_tokens = (
            max_completion_tokens_override
            if max_completion_tokens_override is not None
            else (min(settings.llm_max_tokens, 1800) if verificacion else settings.llm_max_tokens)
        )

        for intento in range(2):
            try:
                respuesta = cliente.chat.completions.create(
                    model=settings.llm_model,
                    temperature=0.0 if verificacion else settings.llm_temperature,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=limite_tokens,
                    reasoning_effort=esfuerzo,
                    response_format={"type": "json_object"} if json else omit,
                )
                break
            except Exception as exc:
                nombre_error = type(exc).__name__
                espera = None
                if nombre_error == "RateLimitError" or getattr(exc, "status_code", None) == 429:
                    coincidencia = re.search(
                        r"try again in ([0-9]+(?:\.[0-9]+)?)\s*ms",
                        str(exc),
                        flags=re.IGNORECASE,
                    )
                    if coincidencia:
                        espera = float(coincidencia.group(1)) / 1000.0
                if intento == 0 and espera is not None and 0 <= espera <= 1.5:
                    time.sleep(espera + 0.1)
                    continue
                raise

        opciones = getattr(respuesta, "choices", None) or []
        mensaje = getattr(opciones[0], "message", None) if opciones else None
        contenido = getattr(mensaje, "content", None)
        return limpiar_salida_llm(contenido).strip() if isinstance(contenido, str) else ""

    except LLMServiceError:
        raise
    except Exception as exc:
        logger.exception("Error al llamar a Groq (%s)", "verificación" if verificacion else "respuesta")
        raise clasificar_error_groq(exc) from exc


def generar_respuesta(prompt: str) -> str:
    """Envía el prompt a Groq y devuelve el texto de la respuesta."""
    texto = _llamar_groq(prompt)
    # Si el LLM devuelve vacío, se responde como "sin evidencia".
    if not texto:
        logger.warning("Groq devolvió una respuesta vacía")
        return "No hay evidencia suficiente para responder. Se recomienda escalar la incidencia."
    return texto


def generar_verificacion(prompt: str) -> str:
    """Hace una segunda pasada breve para revisar afirmaciones documentales.

    El resultado lo valida después `services.verificacion`; no se considera fiable
    sin comprobar sus citas contra el texto fuente.
    """
    from .errores_llm import LLMServiceError

    texto = _llamar_groq(prompt, verificacion=True, json=True)
    if not texto:
        raise LLMServiceError(
            "empty_verification_response",
            "El verificador no devolvió contenido.",
            retryable=True,
        )
    return texto


def generar_evaluacion_suficiencia(prompt: str) -> str:
    """Evalúa la cobertura documental antes de generar la respuesta RAG (R07).

    Usa el canal de verificación (temperatura baja/cero y límite breve de tokens).
    La salida JSON y sus citas se validan después en `services.suficiencia_evidencia`.
    """
    from .errores_llm import LLMServiceError

    texto = _llamar_groq(
        prompt,
        verificacion=True,
        # Incluye el razonamiento interno de gpt-oss y citas literales: con 700 el JSON
        # se cortaba a medias y R07 fallaba.
        max_completion_tokens_override=1500,
        reasoning_effort_override="low",
        json=True,
    )
    if not texto:
        raise LLMServiceError(
            "empty_sufficiency_response",
            "El evaluador de suficiencia no devolvió contenido.",
            retryable=True,
        )
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
        "lo que corresponda).\n"
        "Si la nueva pregunta ya se entiende sola, devuélvela EXACTAMENTE igual, sin "
        "cambiar ninguna palabra: no la parafrasees (cambiar «cada cuántos km» por «con "
        "qué frecuencia» empeora la búsqueda).\n"
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
            "REGLAS ESTRICTAS:\n"
            "- Conserva todos los códigos y datos originales de la pregunta.\n"
            "- Añade solo términos del glosario que nombren lo MISMO que ya pregunta el usuario.\n"
            "- NO respondas a la pregunta: no añadas pasos, comprobaciones, causas, valores ni "
            "componentes que el usuario no mencione (eso desvía la búsqueda).\n"
            "- Devuelve ÚNICAMENTE la consulta enriquecida en una sola frase, sin comillas ni explicaciones.\n\n"
            f"Glosario aplicable:\n{glosario_contexto}\n\n"
            f"Consulta original: {mensaje}\n\n"
            "Consulta técnica enriquecida:"
        )

        consulta_reescrita = generar_respuesta(prompt_traduccion).strip()

        if not consulta_reescrita or "No hay evidencia suficiente" in consulta_reescrita:
            return mensaje
        # Si el modelo no ha añadido nada, no se duplica la pregunta: "X (X)".
        if " ".join(consulta_reescrita.split()).casefold() == " ".join(mensaje.split()).casefold():
            return mensaje

        # Mantenemos el mensaje original + la traducción técnica para no perder palabras clave en la búsqueda
        return f"{mensaje} ({consulta_reescrita})"

    except Exception:
        logger.warning("Fallo al traducir la consulta; se mantiene el mensaje original.")
        return mensaje