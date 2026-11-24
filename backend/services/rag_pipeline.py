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

Funciones de este fichero:
  validar_consulta  limpia el mensaje y comprueba que la versión del motor exista.
  armar_respuesta   ejecuta el flujo completo y devuelve la respuesta de la API.

Flujo de una consulta:

  pregunta + versión
      -> validar_consulta            limpia el mensaje y comprueba la versión
      -> reformular_con_historial    hace que una pregunta de seguimiento se entienda sola
      -> traducir_consulta           pasa el lenguaje coloquial a términos técnicos
      -> buscar_fragmentos           busca los fragmentos más parecidos (usa cargar_fragmentos)
      -> evaluar_suficiencia_evidencia comprueba cobertura documental (R07)
      -> construir_prompt            junta reglas + fragmentos validados + pregunta
      -> generar_respuesta           llama al LLM (Groq)
      -> construir_fuentes           prepara las fuentes para el frontend
      -> armar_respuesta             orquesta todo (usa respuesta_sin_evidencia / pedir_aclaracion)

Configuración (backend/config.py -> `from config import settings`, valores en el .env):
  settings.rag_top_k, settings.rag_evidence_min_score, settings.rag_evidence_high_score
  (el resto de valores los usan los demás módulos).
Modelos del contrato de la API: models/schemas.py (ChatResponse, Source, ...).
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from config import ENGINE_VERSIONS, settings

from .llm import generar_respuesta, reformular_con_historial, traducir_consulta
from .coherencia_version import detectar_incoherencia_version, respuesta_aclaracion_version
from .ambiguedad import (
    detectar_aclaracion_tecnica,
    hay_aclaracion_tecnica_pendiente,
    consulta_autonoma_tras_aclaracion,
    respuesta_aclaracion_tecnica,
)
from .prompts import construir_prompt
from .pasos import paso_busqueda, paso_conclusion, paso_cobertura, paso_transformacion
from .respuestas import (
    construir_fuentes,
    extraer_referencias_citadas,
    pedir_aclaracion,
    respuesta_sin_evidencia,
    respuesta_limitada_por_verificacion,
    normalizar_intervalos_caudal,
)
from .retrieval import anadir_notas_de_alcance, buscar_fragmentos
from .safety import evaluar_alertas_seguridad
from .verificacion import (
    resultado_verificacion_no_disponible,
    resultado_verificacion_no_ejecutada,
    verificar_afirmaciones,
)
from .suficiencia_evidencia import (
    evaluar_suficiencia_evidencia,
    fragmentos_con_evidencia_validada,
    resultado_suficiencia_no_disponible,
    resultado_suficiencia_no_ejecutada,
)

logger = logging.getLogger(__name__)


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
    # 1. Aplicar la capa determinista de seguridad ANTES de consultar al LLM.
    # Se evalúa incluso si falta la versión o la recuperación no encuentra evidencia.
    mensaje_limpio, version_canonica = validar_consulta(mensaje, version)
    alertas_seguridad = evaluar_alertas_seguridad(mensaje_limpio, historial)

    # Versión vacía o desconocida: pedir que la elija, sin llamar al LLM.
    # Los avisos de seguridad no dependen de que el usuario haya seleccionado versión.
    if version_canonica is None:
        resultado = pedir_aclaracion(version)
        resultado["clarification_kind"] = "engine_version"
        resultado["safety_alerts"] = alertas_seguridad
        resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
        return resultado

    # 1a. Coherencia de versiones: el selector identifica la versión del vehículo.
    # Si la pregunta menciona otra, o varias versiones, no recuperamos documentos
    # ni llamamos al LLM hasta que el usuario elija una única versión coherente.
    incoherencia_version = detectar_incoherencia_version(mensaje_limpio, version_canonica)
    if incoherencia_version is not None:
        resultado = respuesta_aclaracion_version(incoherencia_version, alertas_seguridad)
        resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
        return resultado

    # 1b. R06: detectar ambigüedades técnicas concretas antes de reformular,
    # recuperar o llamar al LLM. Si el último turno fue una aclaración técnica,
    # no se vuelve a preguntar: se deja que el historial ayude a resolver el seguimiento.
    if (
        getattr(settings, "rag_ambiguity_detection_enabled", False)
        and not hay_aclaracion_tecnica_pendiente(historial)
    ):
        aclaracion = detectar_aclaracion_tecnica(mensaje_limpio)
        if aclaracion is not None:
            resultado = respuesta_aclaracion_tecnica(aclaracion, alertas_seguridad)
            resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
            return resultado

    # 2. Reformular con el historial (para preguntas de seguimiento) y pasar
    #    la pregunta a lenguaje técnico. Ambas versiones solo sirven para buscar.
    # Si el usuario está respondiendo a una aclaración técnica, combinar la pregunta
    # original y la precisión aportada de forma determinista. Para otros seguimientos
    # se mantiene la reformulación LLM habitual.
    aclaracion_pendiente = hay_aclaracion_tecnica_pendiente(historial)
    if aclaracion_pendiente:
        pregunta_autonoma = consulta_autonoma_tras_aclaracion(mensaje_limpio, historial)
        if pregunta_autonoma is None:
            # La respuesta no identifica ninguna opción de forma inequívoca.
            # Repetimos la aclaración y no permitimos que el LLM adivine.
            resultado = respuesta_aclaracion_tecnica(
                {"message": str(historial[-1].get("content", "¿Puedes concretar tu elección?"))},
                alertas_seguridad,
            )
            resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
            return resultado
        # La pregunta contextual y la selección explícita deben llegar tanto al
        # recuperador como al prompt final. Enviar solo «La bomba A» al LLM
        # hacía que volviera a preguntar qué bomba debía comprobar.
        mensaje_para_prompt = pregunta_autonoma
    else:
        pregunta_autonoma = reformular_con_historial(mensaje_limpio, historial)
        mensaje_para_prompt = mensaje_limpio

    consulta_tecnica = traducir_consulta(pregunta_autonoma)
    fecha_consulta = datetime.now().astimezone()
    pasos = [paso_transformacion(
        version_canonica,
        perfil,
        mensaje_limpio,
        pregunta_autonoma,
        consulta_tecnica,
        fecha_consulta,
    )]

    # 3. Buscar los fragmentos más relevantes de esa versión.
    fragmentos = buscar_fragmentos(
        consulta_tecnica,
        version_canonica,
        settings.rag_top_k,
    )

    # La recuperación ordena por ranking_score, que puede incluir bonificaciones
    # léxicas (por ejemplo, coincidencia exacta de un código DTC). La evidencia,
    # en cambio, debe basarse en la mayor similitud semántica pura de los fragmentos
    # que realmente se entregarán al modelo, no en el primero de la lista ordenada.
    mejor_score_semantico = max(
        (float(fragmento["score"]) for fragmento in fragmentos),
        default=0.0,
    )
    # Si ningún fragmento se parece lo suficiente (o no hay), no se llama al LLM.
    if mejor_score_semantico < settings.rag_evidence_min_score:
        pasos.append(paso_busqueda(version_canonica, fragmentos, set()))
        pasos.append(paso_conclusion(
            "insufficient",
            mejor_score_semantico,
            settings.rag_evidence_min_score,
            settings.rag_evidence_high_score,
            detalle_extra=(
                f"La mejor similitud ({mejor_score_semantico:.2f}) no alcanza el mínimo "
                f"configurado ({settings.rag_evidence_min_score:.2f}); no se llamó al generador."
            ),
        ))
        resultado = respuesta_sin_evidencia()
        resultado["steps"] = pasos
        resultado["safety_alerts"] = alertas_seguridad
        resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
        resultado["evidence_sufficiency"] = resultado_suficiencia_no_ejecutada()
        return resultado

    # R07: la similitud solo indica relación temática. Antes de generar, comprobamos
    # que los fragmentos contienen los datos concretos que solicita la pregunta.
    suficiencia = resultado_suficiencia_no_ejecutada()
    fragmentos_evaluacion = fragmentos
    fragmentos_contexto = fragmentos
    instruccion_suficiencia = None
    if getattr(settings, "rag_evidence_sufficiency_enabled", False):
        fragmentos_evaluacion = anadir_notas_de_alcance(
            pregunta_autonoma, fragmentos, version_canonica
        )
        try:
            suficiencia = evaluar_suficiencia_evidencia(
                pregunta_autonoma, fragmentos_evaluacion
            )
        except Exception:
            # Fail-closed: si no podemos evaluar cobertura, no dejamos que el generador
            # responda basándose únicamente en la similitud temática.
            logger.exception("No se pudo comprobar la suficiencia documental (R07)")
            resultado = respuesta_sin_evidencia()
            resultado["message"]["content"] = (
                "No he podido comprobar si la documentación recuperada contiene los datos "
                "necesarios para responder. Para evitar darte una especificación no verificada, "
                "no voy a estimarla. Inténtalo de nuevo más tarde o consulta al equipo de soporte."
            )
            resultado["safety_alerts"] = alertas_seguridad
            resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
            resultado["evidence_sufficiency"] = resultado_suficiencia_no_disponible()
            resultado["documents_consulted"] = len({
                str(fragmento.get("chunk_id", "")).rsplit("_", 1)[0]
                for fragmento in fragmentos if fragmento.get("chunk_id")
            })
            pasos.append(paso_busqueda(version_canonica, fragmentos, set()))
            pasos.append(paso_cobertura(resultado["evidence_sufficiency"]))
            pasos.append(paso_conclusion(
                "insufficient", mejor_score_semantico,
                settings.rag_evidence_min_score, settings.rag_evidence_high_score,
                detalle_extra="La comprobación de cobertura no estuvo disponible; se bloqueó la generación.",
            ))
            resultado["steps"] = pasos
            return resultado

        if suficiencia["status"] == "insufficient":
            faltantes = suficiencia.get("missing_information", [])
            detalle = "; ".join(faltantes[:6])
            texto = (
                "No hay evidencia suficiente en la documentación para responder a esta consulta. "
                "Los fragmentos recuperados están relacionados con el tema, pero no permiten "
                "establecer con fiabilidad los datos concretos solicitados."
            )
            if detalle:
                texto += f" Información no localizada: {detalle}."
            texto += " No voy a estimar ni completar esos datos. Se recomienda consultar la documentación oficial o escalar la consulta al equipo de soporte."
            return {
                "message": {"id": str(uuid.uuid4()), "role": "assistant", "content": texto},
                "evidence_status": "insufficient",
                "sources": [],
                "documents_consulted": len({
                    str(fragmento.get("chunk_id", "")).rsplit("_", 1)[0]
                    for fragmento in fragmentos if fragmento.get("chunk_id")
                }),
                "needs_clarification": False,
                "safety_alerts": alertas_seguridad,
                "claim_verification": resultado_verificacion_no_ejecutada(),
                "evidence_sufficiency": suficiencia,
                "steps": pasos + [
                    paso_busqueda(version_canonica, fragmentos, set()),
                    paso_cobertura(suficiencia),
                    paso_conclusion(
                        "insufficient", mejor_score_semantico,
                        settings.rag_evidence_min_score, settings.rag_evidence_high_score,
                        detalle_extra="R07 no encontró evidencia suficiente para los datos solicitados; se omitió la generación.",
                    ),
                ],
            }

        # El generador solo recibirá fragmentos que contienen una cita literal validada
        # para alguno de los elementos solicitados como supported.
        fragmentos_contexto = fragmentos_con_evidencia_validada(fragmentos_evaluacion, suficiencia)
        if not fragmentos_contexto:
            logger.error("R07 indicó cobertura, pero no quedaron fragmentos con evidencia validada")
            resultado = respuesta_sin_evidencia()
            resultado["safety_alerts"] = alertas_seguridad
            resultado["claim_verification"] = resultado_verificacion_no_ejecutada()
            resultado["evidence_sufficiency"] = resultado_suficiencia_no_disponible()
            resultado["documents_consulted"] = len({
                str(fragmento.get("chunk_id", "")).rsplit("_", 1)[0]
                for fragmento in fragmentos if fragmento.get("chunk_id")
            })
            pasos.append(paso_busqueda(version_canonica, fragmentos, set()))
            pasos.append(paso_cobertura(resultado["evidence_sufficiency"]))
            pasos.append(paso_conclusion(
                "insufficient", mejor_score_semantico,
                settings.rag_evidence_min_score, settings.rag_evidence_high_score,
                detalle_extra="R07 indicó cobertura positiva, pero no quedaron fragmentos con citas literales validadas.",
            ))
            resultado["steps"] = pasos
            return resultado

        if suficiencia["status"] == "partial":
            respaldados = [
                item["item"] for item in suficiencia["requested_items"]
                if item["status"] == "supported"
            ]
            no_respaldados = suficiencia.get("missing_information", [])
            instruccion_suficiencia = (
                "La cobertura documental es PARCIAL. Responde exclusivamente a estos aspectos "
                "respaldados: " + "; ".join(respaldados) + ". "
                "No afirmes ni deduzcas los siguientes datos porque no están respaldados: "
                + ("; ".join(no_respaldados) if no_respaldados else "los restantes aspectos solicitados")
                + ". Indica expresamente que no hay evidencia suficiente en la documentación "
                "para esos datos y no los estimes."
            )

    # El score final y las fuentes se calculan sobre los fragmentos que realmente
    # se entregan al generador, no sobre los que R07 ha descartado.
    mejor_score_semantico = max(
        (float(fragmento["score"]) for fragmento in fragmentos_contexto),
        default=0.0,
    )

    # 5. Construir el prompt. En turnos normales se conserva el mensaje original.
    #    Si R07 es parcial, el prompt limita explícitamente la respuesta a los datos probados.
    prompt_final = construir_prompt(
        mensaje_para_prompt,
        fragmentos_contexto,
        perfil,
        historial,
        version_canonica,
        instruccion_suficiencia,
    )

    # 6. Obtener la respuesta del LLM.
    # Si hay una señal crítica y el proveedor falla, se devuelve un mensaje preventivo
    # determinista junto con las alertas; así el aviso no desaparece por un error de Groq.
    try:
        texto_respuesta = generar_respuesta(prompt_final)
        texto_respuesta = normalizar_intervalos_caudal(texto_respuesta)
    except Exception:
        if not alertas_seguridad:
            raise
        return {
            "message": {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": (
                    "No se ha podido generar una respuesta técnica en este momento. "
                    "No realices comprobaciones ni reparaciones basándote en una respuesta "
                    "incompleta; sigue los avisos preventivos y consulta la documentación "
                    "oficial o a un profesional cualificado."
                ),
            },
            "evidence_status": "insufficient",
            "sources": [],
            "documents_consulted": 0,
            "needs_clarification": False,
            "safety_alerts": alertas_seguridad,
            "claim_verification": resultado_verificacion_no_ejecutada(),
            "evidence_sufficiency": suficiencia,
            "steps": pasos + [
                paso_busqueda(version_canonica, fragmentos, set()),
                paso_cobertura(suficiencia),
                paso_conclusion(
                    "insufficient", mejor_score_semantico,
                    settings.rag_evidence_min_score, settings.rag_evidence_high_score,
                    detalle_extra="No se pudo generar la respuesta técnica; se mantienen los avisos preventivos.",
                ),
            ],
        }

    # evidence_status: insuficiente si el propio LLM dice que no hay
    # evidencia; si no, alta o media según el mejor score.
    if suficiencia["status"] == "partial":
        # La consulta sí contiene una parte respondible; el estado de cobertura
        # parcial se expone por separado y no se degrada toda la respuesta a insuficiente.
        evidencia = "medium"
    elif "no hay evidencia suficiente" in texto_respuesta.lower():
        evidencia = "insufficient"
    elif mejor_score_semantico >= settings.rag_evidence_high_score:
        evidencia = "high"
    else:
        evidencia = "medium"

    # 7. Segunda pasada opcional: revisa afirmaciones frente a los fragmentos que recibió el modelo.
    # Si hay afirmaciones sin respaldo, la respuesta se limita de forma determinista a las
    # que tengan una cita literal validada. Si el verificador falla, se conserva la respuesta
    # original y se marca la revisión como no disponible: no se inventa una corrección.
    claim_verification = resultado_verificacion_no_ejecutada()
    if getattr(settings, "rag_claim_verification_enabled", False) and evidencia != "insufficient":
        try:
            claim_verification = verificar_afirmaciones(texto_respuesta, fragmentos_contexto)
        except Exception:
            logger.exception("No se pudo completar la verificación de afirmaciones; se conserva la respuesta RAG")
            claim_verification = resultado_verificacion_no_disponible()

    referencias_citadas = extraer_referencias_citadas(texto_respuesta, len(fragmentos_contexto))
    if claim_verification.get("status") == "needs_review":
        texto_respuesta, referencias_citadas = respuesta_limitada_por_verificacion(
            claim_verification,
            fragmentos_contexto,
        )
        claim_verification["answer_restricted"] = True
        # Si no queda ninguna afirmación respaldada, la respuesta final se considera insuficiente.
        if not referencias_citadas:
            evidencia = "insufficient"
        else:
            evidencia = "medium"

    # Las fuentes y la traza se construyen después de la revisión para reflejar el texto final.
    fuentes = construir_fuentes(fragmentos_contexto, version_canonica, referencias_citadas)
    if claim_verification.get("answer_restricted"):
        for indice, fuente in enumerate(fuentes, start=1):
            if indice in referencias_citadas:
                fuente["citation_status"] = "verified"
    ids_citados = {
        fuente["id"] for fuente in fuentes
        if fuente.get("citation_status") in {"cited", "verified"}
    }
    pasos.append(paso_busqueda(version_canonica, fragmentos, ids_citados))
    cobertura_paso = paso_cobertura(suficiencia)
    if cobertura_paso is not None:
        pasos.append(cobertura_paso)

    # Se mantiene el recuento de todos los documentos recuperados que recibió el modelo.
    documentos = {fuente["document"] for fuente in fuentes}

    pasos.append(paso_conclusion(
        evidencia,
        mejor_score_semantico,
        settings.rag_evidence_min_score,
        settings.rag_evidence_high_score,
        fuentes=len(ids_citados),
        documentos=len({fuente["document"] for fuente in fuentes if fuente.get("citation_status") in {"cited", "verified"}}),
    ))

    return {
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": texto_respuesta,
        },
        "steps": pasos,
        "evidence_status": evidencia,
        "sources": fuentes,
        "documents_consulted": len(documentos),
        "needs_clarification": False,
        "safety_alerts": alertas_seguridad,
        "claim_verification": claim_verification,
        "evidence_sufficiency": suficiencia,
    }
