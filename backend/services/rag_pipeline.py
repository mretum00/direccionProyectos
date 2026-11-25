"""
Proceso de consulta RAG de ThermoDrive (orquestador).

Recibe la pregunta del usuario, busca en la documentación técnica los fragmentos
más relevantes para su versión del motor y pide al LLM una respuesta basada
solo en esos fragmentos. Lo usa el endpoint POST /api/chat
(routers/chat.py llama a `armar_respuesta`).

Este fichero solo une las piezas; cada una vive en su propio módulo
(todos en backend/services/):

  safety.py                avisos de seguridad deterministas
  coherencia_version.py    versión escrita en la pregunta frente a la del selector
  ambiguedad.py            preguntas técnicas ambiguas ("la bomba") (R06)
  llm.py                   reformular la pregunta y hablar con Groq
  retrieval.py             buscar los fragmentos más parecidos
  suficiencia_evidencia.py ¿cubren los fragmentos lo que se pregunta? (R07)
  prompts.py               construir el prompt final
  verificacion.py          segunda pasada que revisa las afirmaciones
  pasos.py                 fases visibles del proceso (campo `steps`)
  respuestas.py            forma única de las respuestas y fuentes

Flujo de una consulta (cada fase puede terminar la consulta antes de tiempo):

  1. Comprobaciones previas -> aclaración si falta la versión, no coincide con
                               la de la pregunta o la pregunta es ambigua.
  2. Preparar la pregunta   -> reformular con el historial y pasar a lenguaje técnico.
  3. Buscar                 -> sin evidencia si ningún fragmento se parece.
  4. Cobertura (R07)        -> sin evidencia si los fragmentos no contienen los
                               datos pedidos.
  5. Generar                -> respuesta del LLM con los fragmentos validados.
  6. Revisar y cerrar       -> verificación de afirmaciones, fuentes y pasos.

Todas las salidas usan `respuestas.nueva_respuesta`, así que siempre tienen los
mismos campos (formato ChatResponse de models/schemas.py).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple, Optional

from config import ENGINE_VERSIONS, settings

from .ambiguedad import (
    consulta_autonoma_tras_aclaracion,
    detectar_aclaracion_tecnica,
    pregunta_de_busqueda_tras_aclaracion,
    respuesta_aclaracion_tecnica,
    responde_a_aclaracion,
    seleccion_tras_aclaracion,
)
from .coherencia_version import detectar_incoherencia_version, respuesta_aclaracion_version
from .errores_llm import LLMServiceError
from .llm import generar_respuesta, reformular_con_historial, traducir_consulta
from .pasos import (
    comprobacion,
    paso_busqueda,
    paso_cobertura,
    paso_comprobaciones,
    paso_conclusion,
    paso_transformacion,
)
from .prompts import construir_prompt
from .respuestas import (
    TEXTO_SIN_EVIDENCIA,
    construir_fuentes,
    contar_documentos,
    extraer_referencias_citadas,
    normalizar_intervalos_caudal,
    nueva_respuesta,
    pedir_aclaracion,
    respuesta_limitada_por_verificacion,
    respuesta_sin_evidencia,
)
from .retrieval import anadir_notas_de_alcance, buscar_fragmentos
from .safety import evaluar_alertas_seguridad
from .suficiencia_evidencia import (
    evaluar_suficiencia_evidencia,
    fragmentos_con_evidencia_validada,
    resultado_suficiencia_no_disponible,
    resultado_suficiencia_no_ejecutada,
)
from .verificacion import (
    resultado_verificacion_no_disponible,
    resultado_verificacion_no_ejecutada,
    verificar_afirmaciones,
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


# --- Textos fijos de las respuestas sin evidencia ------------------------------

TEXTO_COBERTURA_NO_DISPONIBLE = (
    "No he podido comprobar si la documentación recuperada contiene los datos "
    "necesarios para responder. Para evitar darte una especificación no verificada, "
    "no voy a estimarla. Inténtalo de nuevo más tarde o consulta al equipo de soporte."
)

TEXTO_FALLO_GENERACION = (
    "No se ha podido generar una respuesta técnica en este momento. "
    "No realices comprobaciones ni reparaciones basándote en una respuesta "
    "incompleta; sigue los avisos preventivos y consulta la documentación "
    "oficial o a un profesional cualificado."
)


def _texto_cobertura_insuficiente(faltantes: list[str]) -> str:
    texto = (
        "No hay evidencia suficiente en la documentación para responder a esta consulta. "
        "Los fragmentos recuperados están relacionados con el tema, pero no permiten "
        "establecer con fiabilidad los datos concretos solicitados."
    )
    if faltantes:
        texto += f" Información no localizada: {'; '.join(faltantes[:6])}."
    return texto + (
        " No voy a estimar ni completar esos datos. Se recomienda consultar la "
        "documentación oficial o escalar la consulta al equipo de soporte."
    )


def _mejor_score(fragmentos: list[dict]) -> float:
    """Mayor similitud semántica pura de los fragmentos.

    La recuperación ordena por ranking_score, que puede incluir bonificaciones
    léxicas (p. ej. coincidencia exacta de un código DTC). La evidencia se basa en
    la similitud semántica, no en el primero de la lista ordenada.
    """
    return max((float(fragmento["score"]) for fragmento in fragmentos), default=0.0)


# --- Estado de una consulta que ya ha llegado a la búsqueda ----------------------


@dataclass
class _Consulta:
    """Lo que se va sabiendo de la consulta a partir de la búsqueda.

    Permite cerrar la consulta sin respuesta desde cualquier fase con la misma
    forma: pasos de búsqueda, cobertura y conclusión, y evidencia insuficiente.
    """

    version: str
    alertas: list[dict]
    pasos: list[dict]
    fragmentos: list[dict] = field(default_factory=list)
    mejor_score: float = 0.0

    def sin_respuesta(self, texto: str, motivo: str, suficiencia: Optional[dict] = None) -> dict:
        """Termina la consulta sin llamar (o sin poder usar) al generador."""
        suficiencia = suficiencia or resultado_suficiencia_no_ejecutada()
        pasos = [*self.pasos, paso_busqueda(self.version, self.fragmentos, set())]
        cobertura = paso_cobertura(suficiencia)
        if cobertura is not None:
            pasos.append(cobertura)
        pasos.append(paso_conclusion(
            "insufficient",
            self.mejor_score,
            settings.rag_evidence_min_score,
            settings.rag_evidence_high_score,
            detalle_extra=motivo,
        ))
        return respuesta_sin_evidencia(
            texto,
            pasos=pasos,
            alertas=self.alertas,
            suficiencia=suficiencia,
            documentos=contar_documentos(self.fragmentos),
        )


class _Cobertura(NamedTuple):
    """Resultado de la fase 4: qué fragmentos llegan al generador y con qué límites."""

    suficiencia: dict
    fragmentos: list[dict]
    instruccion: Optional[str] = None
    # Si no es None, la consulta termina aquí con esta respuesta.
    respuesta: Optional[dict] = None


# --- Fases ------------------------------------------------------------------------


class _Previas(NamedTuple):
    """Resultado de la fase 1: resultados de cada comprobación y, si se detiene, la aclaración."""

    resultados: list[dict]
    # Si no es None, la consulta termina aquí con esta aclaración.
    respuesta: Optional[dict] = None


def _comprobaciones_previas(
    mensaje: str,
    version_recibida: str,
    version: Optional[str],
    respondiendo_aclaracion: bool,
    alertas: list[dict],
) -> _Previas:
    """Fase 1: ¿hay que pedir algo al usuario antes de buscar? Ninguna llama al LLM.

    Cada comprobación deja su resultado para el paso "Comprobaciones previas" que se
    muestra en "Pasos seguidos", también cuando la consulta se detiene en ella.
    """
    resultados: list[dict] = []

    # Versión vacía o desconocida: que la elija en el selector.
    if version is None:
        texto = (
            f"Versión «{version_recibida.strip()}» no reconocida"
            if version_recibida.strip()
            else "Falta elegir la versión del motor en el selector"
        )
        resultados.append(comprobacion(texto, "stop"))
        return _Previas(resultados, pedir_aclaracion(version_recibida, alertas))
    resultados.append(comprobacion(f"Versión del motor elegida en el selector: {version}", "ok"))

    # El selector identifica la versión del vehículo. Si la pregunta menciona otra,
    # o varias, se pide una única versión coherente.
    incoherencia = detectar_incoherencia_version(mensaje, version)
    if incoherencia is not None:
        versiones = ", ".join(incoherencia.get("versions", []))
        texto = (
            f"La pregunta menciona varias versiones ({versiones}); se consulta una sola por turno"
            if incoherencia["kind"] == "version_comparison"
            else f"La pregunta menciona {incoherencia.get('mentioned_version')} y el selector tiene {version}"
        )
        resultados.append(comprobacion(texto, "stop"))
        return _Previas(resultados, respuesta_aclaracion_version(incoherencia, alertas))
    resultados.append(comprobacion("La pregunta no contradice la versión seleccionada", "ok"))

    # R06: pregunta técnica ambigua ("la bomba"). Si el usuario está contestando
    # a una aclaración técnica no se vuelve a preguntar: la fase 2 la resuelve.
    if respondiendo_aclaracion:
        resultados.append(comprobacion("Respuesta a la aclaración técnica anterior", "ok"))
    elif not getattr(settings, "rag_ambiguity_detection_enabled", False):
        resultados.append(comprobacion("Detección de preguntas ambiguas desactivada", "skipped"))
    else:
        aclaracion = detectar_aclaracion_tecnica(mensaje)
        if aclaracion is not None:
            resultados.append(comprobacion(
                "La pregunta es ambigua: puede referirse a varios componentes", "stop"
            ))
            return _Previas(resultados, respuesta_aclaracion_tecnica(aclaracion, alertas))
        resultados.append(comprobacion("La pregunta no es ambigua", "ok"))

    return _Previas(resultados)


class _Pregunta(NamedTuple):
    """Resultado de la fase 2."""

    busqueda: str  # pregunta autónoma para buscar y evaluar la cobertura
    prompt: str  # pregunta que recibe el generador
    aclaracion: Optional[str] = None  # opción elegida en una aclaración técnica


def _preparar_pregunta(
    mensaje: str,
    historial: list[dict],
    respondiendo_aclaracion: bool,
) -> Optional[_Pregunta]:
    """Fase 2: pregunta para buscar y pregunta para el prompt.

    Si el usuario responde a una aclaración técnica, se combina de forma determinista
    la pregunta original con la opción elegida: a la búsqueda va solo la pregunta con
    la opción, y al prompt además la instrucción de no volver a preguntar (enviar
    solo «La bomba A» hacía que el LLM volviera a preguntar). Devuelve None si la
    respuesta no elige ninguna opción.
    Para el resto de seguimientos se usa la reformulación con el LLM.
    """
    if respondiendo_aclaracion:
        resuelta = seleccion_tras_aclaracion(mensaje, historial)
        if resuelta is None:
            return None
        return _Pregunta(
            pregunta_de_busqueda_tras_aclaracion(*resuelta),
            consulta_autonoma_tras_aclaracion(mensaje, historial),
            aclaracion=resuelta[1],
        )
    return _Pregunta(reformular_con_historial(mensaje, historial), mensaje)


def _comprobar_cobertura(pregunta: str, consulta: _Consulta) -> _Cobertura:
    """Fase 4 (R07): ¿contienen los fragmentos los datos concretos que se piden?

    La similitud solo indica relación temática. Si R07 está desactivado, todos los
    fragmentos pasan al generador.
    """
    if not getattr(settings, "rag_evidence_sufficiency_enabled", False):
        return _Cobertura(resultado_suficiencia_no_ejecutada(), consulta.fragmentos)

    fragmentos = anadir_notas_de_alcance(pregunta, consulta.fragmentos, consulta.version)
    try:
        suficiencia = evaluar_suficiencia_evidencia(pregunta, fragmentos)
    except LLMServiceError:
        # Groq no disponible (límite de uso, red...): igual que al generar, el usuario
        # recibe el error del servicio y puede reintentar, en vez de una respuesta
        # guardada que culpa a la documentación. Con avisos de seguridad se sigue
        # respondiendo para que los avisos no se pierdan.
        if not consulta.alertas:
            raise
        logger.exception("Servicio de IA no disponible al comprobar la cobertura (R07)")
        no_disponible = resultado_suficiencia_no_disponible()
        return _Cobertura(no_disponible, [], respuesta=consulta.sin_respuesta(
            TEXTO_FALLO_GENERACION,
            "El servicio de IA no estaba disponible; se mantienen los avisos preventivos.",
            no_disponible,
        ))
    except Exception:
        # Fail-closed: sin comprobar la cobertura no se responde solo por similitud.
        logger.exception("No se pudo comprobar la suficiencia documental (R07)")
        no_disponible = resultado_suficiencia_no_disponible()
        return _Cobertura(no_disponible, [], respuesta=consulta.sin_respuesta(
            TEXTO_COBERTURA_NO_DISPONIBLE,
            "La comprobación de cobertura no estuvo disponible; se bloqueó la generación.",
            no_disponible,
        ))

    if suficiencia["status"] == "insufficient":
        return _Cobertura(suficiencia, [], respuesta=consulta.sin_respuesta(
            _texto_cobertura_insuficiente(suficiencia.get("missing_information", [])),
            "R07 no encontró evidencia suficiente para los datos solicitados; se omitió la generación.",
            suficiencia,
        ))

    # Al generador solo llegan fragmentos con una cita literal validada.
    validados = fragmentos_con_evidencia_validada(fragmentos, suficiencia)
    if not validados:
        logger.error("R07 indicó cobertura, pero no quedaron fragmentos con evidencia validada")
        no_disponible = resultado_suficiencia_no_disponible()
        return _Cobertura(no_disponible, [], respuesta=consulta.sin_respuesta(
            TEXTO_SIN_EVIDENCIA,
            "R07 indicó cobertura positiva, pero no quedaron fragmentos con citas literales validadas.",
            no_disponible,
        ))

    instruccion = None
    if suficiencia["status"] == "partial":
        respaldados = [
            item["item"] for item in suficiencia["requested_items"]
            if item["status"] == "supported"
        ]
        no_respaldados = suficiencia.get("missing_information", [])
        instruccion = (
            "La cobertura documental es PARCIAL. Responde exclusivamente a estos aspectos "
            "respaldados: " + "; ".join(respaldados) + ". "
            "No afirmes ni deduzcas los siguientes datos porque no están respaldados: "
            + ("; ".join(no_respaldados) if no_respaldados else "los restantes aspectos solicitados")
            + ". Indica expresamente que no hay evidencia suficiente en la documentación "
            "para esos datos y no los estimes."
        )
    return _Cobertura(suficiencia, validados, instruccion)


def _nivel_evidencia(texto: str, suficiencia: dict, mejor_score: float) -> str:
    """high / medium / insufficient para la respuesta generada."""
    if suficiencia["status"] == "partial":
        # Hay una parte respondible; la cobertura parcial se muestra aparte.
        return "medium"
    if "no hay evidencia suficiente" in texto.lower():
        return "insufficient"
    if mejor_score >= settings.rag_evidence_high_score:
        return "high"
    return "medium"


# --- Orquestador ------------------------------------------------------------------


def armar_respuesta(mensaje: str, version: str, perfil: str, historial: list[dict]) -> dict:
    """Ejecuta el flujo completo y devuelve un dict con el formato de ChatResponse.

    `historial` son los últimos mensajes del chat ([{"role", "content"}, ...]).
    """
    # Los avisos de seguridad son deterministas y se calculan siempre, antes que
    # nada: acompañan a cualquier tipo de respuesta, también a las aclaraciones.
    mensaje_limpio, version_canonica = validar_consulta(mensaje, version)
    alertas = evaluar_alertas_seguridad(mensaje_limpio, historial)
    # ¿Contesta el usuario a una aclaración técnica anterior ("La bomba A")?
    respondiendo_aclaracion = responde_a_aclaracion(mensaje_limpio, historial)

    # 1. Comprobaciones previas. Las aclaraciones llevan como único paso este resultado.
    previas = _comprobaciones_previas(
        mensaje_limpio, version, version_canonica, respondiendo_aclaracion, alertas
    )
    if previas.respuesta is not None:
        previas.respuesta["steps"] = [paso_comprobaciones(previas.resultados)]
        return previas.respuesta

    # 2. Preparar la pregunta.
    pregunta = _preparar_pregunta(mensaje_limpio, historial, respondiendo_aclaracion)
    if pregunta is None:
        # La respuesta a la aclaración no elige ninguna opción: se repite la pregunta.
        texto_previo = str(historial[-1].get("content", "¿Puedes concretar tu elección?"))
        repetida = respuesta_aclaracion_tecnica({"message": texto_previo}, alertas)
        repetida["steps"] = [paso_comprobaciones([
            *previas.resultados[:-1],
            comprobacion("La respuesta no elige ninguna de las opciones de la aclaración", "stop"),
        ])]
        return repetida
    pregunta_autonoma = pregunta.busqueda

    consulta_tecnica = traducir_consulta(pregunta_autonoma)
    consulta = _Consulta(version_canonica, alertas, pasos=[
        paso_comprobaciones(previas.resultados),
        paso_transformacion(
            version_canonica,
            perfil,
            mensaje_limpio,
            pregunta_autonoma,
            consulta_tecnica,
            datetime.now().astimezone(),
            aclaracion=pregunta.aclaracion,
        ),
    ])

    # 3. Buscar los fragmentos más relevantes de esa versión.
    consulta.fragmentos = buscar_fragmentos(consulta_tecnica, version_canonica, settings.rag_top_k)
    consulta.mejor_score = _mejor_score(consulta.fragmentos)
    if consulta.mejor_score < settings.rag_evidence_min_score:
        return consulta.sin_respuesta(
            TEXTO_SIN_EVIDENCIA,
            f"La mejor similitud ({consulta.mejor_score:.2f}) no alcanza el mínimo "
            f"configurado ({settings.rag_evidence_min_score:.2f}); no se llamó al generador.",
        )

    # 4. Cobertura documental (R07).
    cobertura = _comprobar_cobertura(pregunta_autonoma, consulta)
    if cobertura.respuesta is not None:
        return cobertura.respuesta
    # Desde aquí el score se calcula sobre los fragmentos que recibe el generador.
    consulta.mejor_score = _mejor_score(cobertura.fragmentos)

    # 5. Generar. Si hay un aviso de seguridad y el proveedor falla, se devuelve
    # un mensaje preventivo para que el aviso no desaparezca por un error de Groq.
    prompt_final = construir_prompt(
        pregunta.prompt,
        cobertura.fragmentos,
        perfil,
        historial,
        version_canonica,
        cobertura.instruccion,
    )
    try:
        texto = normalizar_intervalos_caudal(generar_respuesta(prompt_final))
    except Exception:
        if not alertas:
            raise
        return consulta.sin_respuesta(
            TEXTO_FALLO_GENERACION,
            "No se pudo generar la respuesta técnica; se mantienen los avisos preventivos.",
            cobertura.suficiencia,
        )
    evidencia = _nivel_evidencia(texto, cobertura.suficiencia, consulta.mejor_score)

    # 6. Revisar las afirmaciones frente a los fragmentos que recibió el modelo.
    # Si hay afirmaciones sin respaldo, la respuesta se limita a las que tienen una
    # cita literal validada. Si el verificador falla se conserva la respuesta y se
    # marca la revisión como no disponible: no se inventa una corrección.
    verificacion = resultado_verificacion_no_ejecutada()
    if getattr(settings, "rag_claim_verification_enabled", False) and evidencia != "insufficient":
        try:
            verificacion = verificar_afirmaciones(texto, cobertura.fragmentos)
        except Exception:
            logger.exception("No se pudo completar la verificación de afirmaciones; se conserva la respuesta RAG")
            verificacion = resultado_verificacion_no_disponible()

    referencias = extraer_referencias_citadas(texto, len(cobertura.fragmentos))
    if verificacion.get("status") == "needs_review":
        texto, referencias = respuesta_limitada_por_verificacion(verificacion, cobertura.fragmentos)
        verificacion["answer_restricted"] = True
        evidencia = "medium" if referencias else "insufficient"

    # Fuentes y pasos se construyen después de la revisión para reflejar el texto final.
    fuentes = construir_fuentes(cobertura.fragmentos, version_canonica, referencias)
    if verificacion.get("answer_restricted"):
        for indice, fuente in enumerate(fuentes, start=1):
            if indice in referencias:
                fuente["citation_status"] = "verified"
    citadas = [f for f in fuentes if f.get("citation_status") in {"cited", "verified"}]

    pasos = [*consulta.pasos, paso_busqueda(version_canonica, consulta.fragmentos, {f["id"] for f in citadas})]
    paso_r07 = paso_cobertura(cobertura.suficiencia)
    if paso_r07 is not None:
        pasos.append(paso_r07)
    pasos.append(paso_conclusion(
        evidencia,
        consulta.mejor_score,
        settings.rag_evidence_min_score,
        settings.rag_evidence_high_score,
        fuentes=len(citadas),
        documentos=len({f["document"] for f in citadas}),
    ))

    return nueva_respuesta(
        texto,
        evidencia=evidencia,
        fuentes=fuentes,
        # Todos los documentos que recibió el modelo, citados o no.
        documentos=len({f["document"] for f in fuentes}),
        alertas=alertas,
        verificacion=verificacion,
        suficiencia=cobertura.suficiencia,
        pasos=pasos,
    )
