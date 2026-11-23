"""
Proceso de consulta RAG de ThermoDrive (orquestador).

Recibe la pregunta del usuario, busca en la documentación técnica los fragmentos
más relevantes para su versión del motor y pide al LLM una respuesta basada
solo en esos fragmentos. Lo usa el endpoint POST /api/chat
(routers/chat.py llama a `armar_respuesta`).

Este fichero solo une las piezas; cada una vive en su propio módulo
(todos en backend/services/):

  embeddings.py  convertir texto en vectores
  retrieval.py   leer fragmentos de la BD y buscar los más parecidos
  prompts.py     construir el prompt final
  llm.py         hablar con Groq y reescribir la consulta
  respuestas.py  fuentes y respuestas fijas (sin evidencia / aclaración)
  pasos.py       pasos seguidos para llegar a la respuesta (campo `steps`)

Funciones de este fichero:
  validar_consulta  limpia el mensaje y comprueba que la versión del motor exista.
  armar_respuesta   ejecuta el flujo completo y devuelve la respuesta de la API.

Flujo de una consulta:

  pregunta + versión
      -> validar_consulta            limpia el mensaje y comprueba la versión
      -> reformular_con_historial    hace que una pregunta de seguimiento se entienda sola
      -> traducir_consulta           pasa el lenguaje coloquial a términos técnicos
      -> buscar_fragmentos           busca los fragmentos más parecidos (usa cargar_fragmentos)
      -> construir_prompt            junta reglas + fragmentos + pregunta
      -> generar_respuesta           llama al LLM (Groq)
      -> separar_cierre              saca del texto los pasos seguidos y los fragmentos usados
      -> fragmentos_utilizados       se queda solo con los fragmentos de los que salió la respuesta
      -> construir_fuentes           prepara las fuentes para el frontend
      -> armar_respuesta             orquesta todo (usa respuesta_sin_evidencia / pedir_aclaracion)

Configuración (backend/config.py -> `from config import settings`, valores en el .env):
  settings.rag_top_k, settings.rag_evidence_min_score, settings.rag_evidence_high_score
  (el resto de valores los usan los demás módulos).
Modelos del contrato de la API: models/schemas.py (ChatResponse, Source, ...).
"""

import uuid
from typing import Optional

from config import ENGINE_VERSIONS, settings

from .llm import generar_respuesta, reformular_con_historial, traducir_consulta
from .pasos import paso_busqueda, paso_conclusion, paso_razonamiento, paso_transformacion
from .prompts import construir_prompt
from .respuestas import (
    citar_fragmentos,
    construir_fuentes,
    fragmentos_utilizados,
    pedir_aclaracion,
    respuesta_sin_evidencia,
    separar_cierre,
)
from .retrieval import buscar_fragmentos


def validar_consulta(mensaje: str, version: str) -> tuple[str, Optional[str]]:
    """Limpia el mensaje y busca la versión entre las de ENGINE_VERSIONS.

    Devuelve (mensaje_limpio, version_canonica). Si la versión está vacía o no
    existe, version_canonica es None y armar_respuesta pedirá aclaración.
    (Que el mensaje no esté vacío ya lo garantiza ChatRequest.)
    """
    # Comparar sin espacios ni mayúsculas: " v2.0 " -> "V2.0".
    version_limpia = "".join(version.split()).upper()
    canonica = next((v for v in ENGINE_VERSIONS if "".join(v.split()).upper() == version_limpia), None)
    return mensaje.strip(), canonica


def armar_respuesta(mensaje: str, version: str, perfil: str, historial: list[dict]) -> dict:
    """Ejecuta el flujo completo y devuelve un dict con el formato de ChatResponse.

    `historial` son los últimos mensajes del chat ([{"role", "content"}, ...]),
    tal como llegan del frontend.
    """
    # 1. Validar mensaje y versión.
    mensaje_limpio, version_canonica = validar_consulta(mensaje, version)

    # Versión vacía o desconocida: pedir que la elija, sin llamar al LLM.
    if version_canonica is None:
        return pedir_aclaracion(version)

    # 2. Reformular con el historial (para preguntas de seguimiento) y pasar
    #    la pregunta a lenguaje técnico. Ambas versiones solo sirven para buscar.
    pregunta_autonoma = reformular_con_historial(mensaje_limpio, historial)
    consulta_tecnica = traducir_consulta(pregunta_autonoma)

    # Pasos seguidos para llegar a la respuesta (campo `steps`, ver services/pasos.py).
    pasos = [paso_transformacion(version_canonica, perfil, mensaje_limpio, pregunta_autonoma, consulta_tecnica)]

    # 3. Buscar los fragmentos más relevantes de esa versión.
    fragmentos = buscar_fragmentos(
        consulta_tecnica,
        version_canonica,
        settings.rag_top_k,
    )

    # Nivel de evidencia según la similitud del mejor fragmento.
    # Si ninguno se parece lo suficiente (o no hay), no se llama al LLM.
    mejor_score = fragmentos[0]["score"] if fragmentos else 0.0
    if mejor_score < settings.rag_evidence_min_score:
        pasos.append(paso_busqueda(version_canonica, fragmentos, None))
        pasos.append(paso_conclusion(
            "insufficient", mejor_score,
            settings.rag_evidence_min_score, settings.rag_evidence_high_score,
            llamo_al_modelo=False,
        ))
        return respuesta_sin_evidencia(pasos)

    # 5. Construir el prompt. Se usa el mensaje original del usuario, no la
    #    versión traducida (esa solo sirve para buscar).
    prompt_final = construir_prompt(
        mensaje_limpio,
        fragmentos,
        perfil,
        historial,
        version_canonica,
    )

    # 6. Obtener la respuesta del LLM y separar su cierre: los pasos de su
    #    razonamiento y los fragmentos que dice haber usado no van en el texto.
    texto_respuesta, pasos_llm, numeros_usados = separar_cierre(generar_respuesta(prompt_final))
    # Las referencias F1, F2... solo existen en el prompt: se cambian por el documento.
    texto_respuesta = citar_fragmentos(texto_respuesta, fragmentos)

    # evidence_status: insuficiente si el propio LLM dice que no hay
    # evidencia; si no, alta o media según el mejor score.
    if "no hay evidencia suficiente" in texto_respuesta.lower():
        evidencia = "insufficient"
    elif mejor_score >= settings.rag_evidence_high_score:
        evidencia = "high"
    else:
        evidencia = "medium"

    # 7. Preparar las fuentes solo con los fragmentos de los que el LLM ha sacado
    #    la información (no los top_k recuperados) y contar sus documentos.
    usados = fragmentos_utilizados(fragmentos, numeros_usados, texto_respuesta)
    fuentes = construir_fuentes(usados, version_canonica)
    documentos = {fuente["document"] for fuente in fuentes}

    pasos.append(paso_busqueda(version_canonica, fragmentos, usados))
    if (razonamiento := paso_razonamiento(pasos_llm, fragmentos)) is not None:
        pasos.append(razonamiento)
    pasos.append(paso_conclusion(
        evidencia, mejor_score,
        settings.rag_evidence_min_score, settings.rag_evidence_high_score,
        fuentes=len(fuentes), documentos=len(documentos),
    ))

    return {
        "steps": pasos,
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
