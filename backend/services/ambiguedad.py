"""Detección determinista de ambigüedades técnicas en consultas ThermoDrive.

La detección es deliberadamente conservadora: solo solicita aclaraciones en patrones
concretos donde el corpus contiene varias interpretaciones plausibles. No reemplaza
la recuperación RAG ni decide si una respuesta está documentada (R07).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .respuestas import respuesta_aclaracion


_PATRON_CMP = re.compile(r"(?<![A-Z0-9])CMP[-‐‑‒–—− ]?(\d{2})(?!\d)", re.IGNORECASE)
_PATRON_TES = re.compile(r"(?<![A-Z0-9])TES[-‐‑‒–—− ]?(\d{2})(?!\d)", re.IGNORECASE)
_PATRON_CIR = re.compile(r"(?<![A-Z0-9])CIR[-‐‑‒–—− ]?0([123])(?!\d)", re.IGNORECASE)

_INTENCION_PROCEDIMIENTO = (
    "como comprobar",
    "como compruebo",
    "como verificar",
    "como verifico",
    "como probar",
    "como pruebo",
    "como revisar",
    "como reviso",
    "como diagnosticar",
    "como diagnostico",
    "procedimiento",
    "que pasos",
    "de que manera",
    "verificar el funcionamiento",
    "comprobar el funcionamiento",
)

# Atributos que cambian entre CMP-01, CMP-02 y CMP-03. Si se pregunta por uno
# de ellos usando "la bomba" en singular, hay que identificar primero el componente.
_INTENCION_DATO_BOMBA = (
    "caudal",
    "corriente",
    "consumo",
    "amperaje",
    "tension",
    "voltaje",
)


def normalizar(texto: str) -> str:
    """Pasa a minúsculas, elimina tildes y unifica espacios."""
    descompuesto = unicodedata.normalize("NFKD", (texto or "").casefold())
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sin_marcas).split())


def _tiene_codigo(patron: re.Pattern[str], texto: str) -> bool:
    return bool(patron.search(texto or ""))


def _tiene_circuito(texto: str) -> bool:
    return bool(_PATRON_CIR.search(texto or ""))


def _contiene_alguno(texto: str, expresiones: tuple[str, ...]) -> bool:
    return any(expresion in texto for expresion in expresiones)


def hay_aclaracion_tecnica_pendiente(historial: list[dict] | None) -> bool:
    """Indica si el último turno del asistente fue una aclaración técnica.

    El repositorio incluye este dato como metadato de historial. Así no volvemos a
    pedir una aclaración cuando el usuario está contestando a la anterior.
    """
    if not historial:
        return False
    ultimo = historial[-1]
    return (
        ultimo.get("role") == "assistant"
        and ultimo.get("clarification_kind") == "technical"
    )



def _resolver_seleccion_aclaracion(mensaje: str, historial: list[dict]) -> str | None:
    """Interpreta respuestas breves usando las opciones de la aclaración anterior.

    Devuelve una descripción técnica canónica cuando la selección es inequívoca.
    No intenta adivinar ante respuestas vagas: en ese caso el pipeline repite la
    pregunta aclaratoria en vez de consultar al LLM con contexto incompleto.
    """
    if not historial:
        return None

    ultima_aclaracion = normalizar(str(historial[-1].get("content", "")))
    respuesta = normalizar(mensaje)
    respuesta_original = (mensaje or "").strip()
    if not respuesta:
        return None

    codigos_cmp = {f"CMP-{numero}" for numero in _PATRON_CMP.findall(respuesta_original)}
    codigos_cir = {f"CIR-0{numero}" for numero in _PATRON_CIR.findall(respuesta_original)}
    codigos_tes = {f"TES-{numero}" for numero in _PATRON_TES.findall(respuesta_original)}

    # Aclaración de las tres bombas cuando la pregunta original solo dice «la bomba».
    # Se comprueba antes de la variante A/B porque la aclaración de tres opciones
    # también contiene CMP-02 y CMP-03.
    es_aclaracion_tres_bombas = all(
        f"cmp {numero:02d}" in ultima_aclaracion for numero in (1, 2, 3)
    )
    if es_aclaracion_tres_bombas:
        seleccion_01 = (
            "CMP-01" in codigos_cmp
            or "CIR-01" in codigos_cir
            or _contiene_alguno(respuesta, ("mecanica", "bomba del motor", "bomba de motor"))
        )
        seleccion_02 = (
            "CMP-02" in codigos_cmp
            or "CIR-02" in codigos_cir
            or bool(re.search(r"\bbomba(?: auxiliar)? a\b", respuesta))
            or _contiene_alguno(respuesta, ("bateria", "circuito de bateria"))
        )
        seleccion_03 = (
            "CMP-03" in codigos_cmp
            or "CIR-03" in codigos_cir
            or bool(re.search(r"\bbomba(?: auxiliar)? b\b", respuesta))
            or _contiene_alguno(respuesta, ("electronica de potencia", "circuito de electronica"))
        )
        selecciones = [seleccion_01, seleccion_02, seleccion_03]
        if sum(selecciones) != 1:
            return None
        if seleccion_01:
            return "bomba mecánica CMP-01, del circuito térmico del motor CIR-01"
        if seleccion_02:
            return "bomba auxiliar A CMP-02, del circuito de batería CIR-02"
        return "bomba auxiliar B CMP-03, del circuito de electrónica de potencia CIR-03"

    # Aclaración de bomba auxiliar A/B (la bomba mecánica no es una auxiliar).
    es_aclaracion_bomba_ab = (
        ("cmp 02" in ultima_aclaracion and "cmp 03" in ultima_aclaracion)
        or "bomba auxiliar a o b" in ultima_aclaracion
        or ("bomba auxiliar a" in ultima_aclaracion and "bomba auxiliar b" in ultima_aclaracion)
    )
    if es_aclaracion_bomba_ab:
        seleccion_a = (
            "CMP-02" in codigos_cmp
            or "CIR-02" in codigos_cir
            or bool(re.search(r"\bbomba(?: auxiliar)? a\b", respuesta))
            or _contiene_alguno(respuesta, ("bateria", "circuito de bateria"))
        )
        seleccion_b = (
            "CMP-03" in codigos_cmp
            or "CIR-03" in codigos_cir
            or bool(re.search(r"\bbomba(?: auxiliar)? b\b", respuesta))
            or _contiene_alguno(respuesta, ("electronica de potencia", "circuito de electronica"))
        )
        if seleccion_a and not seleccion_b:
            return "bomba auxiliar A (CMP-02), del circuito de batería CIR-02"
        if seleccion_b and not seleccion_a:
            return "bomba auxiliar B (CMP-03), del circuito de electrónica de potencia CIR-03"
        return None

    # Aclaración sobre el sensor concreto.
    if all(f"cmp {numero}" in ultima_aclaracion for numero in ("14", "15", "16", "20")):
        if "CMP-14" in codigos_cmp or "motor" in respuesta:
            return "sensor de temperatura del motor (CMP-14)"
        if "CMP-15" in codigos_cmp or "bateria" in respuesta:
            return "sensor de temperatura de batería (CMP-15)"
        if "CMP-16" in codigos_cmp or "inversor" in respuesta:
            return "sensor de temperatura del inversor (CMP-16)"
        if "CMP-20" in codigos_cmp or "ambiente" in respuesta:
            return "sensor de temperatura ambiente (CMP-20)"
        return None

    # Aclaración sobre circuito térmico.
    if all(f"cir 0{numero}" in ultima_aclaracion for numero in (1, 2, 3)):
        if "CIR-01" in codigos_cir or "motor" in respuesta:
            return "circuito térmico del motor CIR-01"
        if "CIR-02" in codigos_cir or "bateria" in respuesta:
            return "circuito de batería CIR-02"
        if "CIR-03" in codigos_cir or _contiene_alguno(respuesta, ("inversor", "electronica de potencia")):
            return "circuito de electrónica de potencia CIR-03"
        return None

    # Aclaración de testigos: TES-01 y TES-02 pueden mostrarse en amarillo fijo
    # o rojo parpadeante. TES-05, en cambio, siempre exige detención segura y
    # asistencia de personal habilitado. No basta con recibir solo TES-01/TES-02:
    # también necesitamos el estado del testigo para no inferir su urgencia.
    aclaracion_testigos = all(
        f"tes {numero:02d}" in ultima_aclaracion for numero in (1, 2, 5)
    )
    if aclaracion_testigos:
        testigos_seleccionados = codigos_tes.intersection({"TES-01", "TES-02", "TES-05"})
        if len(testigos_seleccionados) != 1:
            return None

        testigo = next(iter(testigos_seleccionados))
        if testigo == "TES-05":
            return "testigo TES-05 de alta tensión; requiere detención segura y personal habilitado"

        rojo_parpadeante = "rojo" in respuesta and _contiene_alguno(
            respuesta, ("parpadea", "parpadeando", "parpadeante")
        )
        amarillo_fijo = "amarillo" in respuesta and _contiene_alguno(
            respuesta, ("fijo", "fija", "sin parpadear")
        )
        if rojo_parpadeante == amarillo_fijo:
            return None

        estado = "rojo parpadeante" if rojo_parpadeante else "amarillo fijo"
        if testigo == "TES-01":
            return f"testigo TES-01 de temperatura de motor, {estado}"
        return f"testigo TES-02 de temperatura de batería de alta tensión, {estado}"

    # Calefacción: conservar el síntoma concreto indicado por el usuario.
    if "calefaccion" in ultima_aclaracion or "calentador ptc" in ultima_aclaracion:
        sintomas = ("no produce calor", "no calienta", "calienta poco", "tarda demasiado", "no sale calor")
        if _contiene_alguno(respuesta, sintomas) or _PATRON_TES.search(respuesta_original) or re.search(r"HTM[- ]?\d{4}", respuesta_original, re.I):
            return f"síntoma de calefacción descrito por el usuario: {respuesta_original}"
        return None

    # Mantenimiento: aceptar un objetivo documental concreto.
    if "mantenimiento" in ultima_aclaracion or "intervalo" in ultima_aclaracion:
        objetivos = {
            "filtro": "filtro del circuito de batería CMP-24",
            "refrigerante": "refrigerante del sistema",
            "bateria": "batería del sistema",
            "electroventilador": "electroventilador CMP-09",
            "valvula": "válvula distribuidora CMP-04",
            "bomba auxiliar a": "bomba auxiliar A CMP-02",
            "bomba auxiliar b": "bomba auxiliar B CMP-03",
        }
        encontrados = [descripcion for clave, descripcion in objetivos.items() if clave in respuesta]
        if len(encontrados) == 1:
            return encontrados[0]
        return None

    # Si el tipo de aclaración no se reconoce, no damos por resuelta la ambigüedad.
    return None


def es_pregunta_nueva(mensaje: str) -> bool:
    """¿Es el mensaje una pregunta completa y no una respuesta breve a la aclaración?

    Una respuesta a «¿A cuál bomba te refieres?» es corta y sin signos de
    interrogación («La A», «No sé»). Una pregunta nueva lleva «?» o es más larga.
    """
    texto = (mensaje or "").strip()
    return "?" in texto or "¿" in texto or len(texto.split()) > 6


def responde_a_aclaracion(mensaje: str, historial: list[dict] | None) -> bool:
    """¿Está el usuario contestando a la aclaración técnica pendiente?

    Sí si elige una opción, o si su mensaje es una respuesta breve (entonces se le
    repite la aclaración en vez de adivinar). Si hace una pregunta nueva, no: se
    trata como cualquier otra consulta y el chat no se queda atascado repitiendo
    la misma aclaración.
    """
    if not hay_aclaracion_tecnica_pendiente(historial):
        return False
    if _resolver_seleccion_aclaracion(mensaje, historial or []) is not None:
        return True
    return not es_pregunta_nueva(mensaje)


def _pregunta_que_origino_la_aclaracion(historial: list[dict]) -> str | None:
    """La pregunta del usuario que provocó la aclaración pendiente.

    Si la aclaración se repitió porque el usuario contestó algo vago
    (pregunta -> aclaración -> «No sé» -> la misma aclaración), la pregunta
    original es la primera, no la respuesta vaga.
    """
    pregunta: str | None = None
    indice = len(historial) - 1
    aclaracion = str(historial[indice].get("content", ""))
    while (
        indice >= 1
        and historial[indice].get("role") == "assistant"
        and historial[indice].get("clarification_kind") == "technical"
        and str(historial[indice].get("content", "")) == aclaracion
        and historial[indice - 1].get("role") == "user"
    ):
        pregunta = str(historial[indice - 1].get("content", "")).strip() or pregunta
        indice -= 2
    return pregunta


def seleccion_tras_aclaracion(mensaje: str, historial: list[dict] | None) -> tuple[str, str] | None:
    """(pregunta original, opción elegida) si el mensaje resuelve la aclaración pendiente."""
    if not hay_aclaracion_tecnica_pendiente(historial):
        return None
    pregunta_original = _pregunta_que_origino_la_aclaracion(historial or [])
    seleccion = _resolver_seleccion_aclaracion(mensaje, historial or [])
    if not pregunta_original or not seleccion:
        return None
    return pregunta_original, seleccion


def pregunta_de_busqueda_tras_aclaracion(pregunta_original: str, seleccion: str) -> str:
    """Pregunta autónoma para buscar y evaluar cobertura: sin instrucciones para el LLM.

    «¿Cómo reviso la bomba?» + «bomba auxiliar A CMP-02...» ->
    «¿Cómo reviso la bomba? (bomba auxiliar A CMP-02...)». Las instrucciones del prompt
    («no vuelvas a solicitarla») no deben llegar a la búsqueda: desvían los embeddings.
    """
    return f"{pregunta_original.strip()} ({seleccion})"


def consulta_autonoma_tras_aclaracion(mensaje: str, historial: list[dict] | None) -> str | None:
    """Combina la pregunta original con una selección técnica inequívoca (para el prompt).

    Una respuesta breve como «La bomba A» se expande a su identificador y circuito.
    Devuelve None si la respuesta no resuelve las opciones; el pipeline repetirá la
    aclaración pendiente en vez de enviar una consulta ambigua al modelo.
    """
    if not hay_aclaracion_tecnica_pendiente(historial):
        return mensaje

    resuelta = seleccion_tras_aclaracion(mensaje, historial)
    if resuelta is None:
        return None
    pregunta_original, seleccion = resuelta
    return (
        f"{pregunta_original}\n"
        f"Aclaración técnica confirmada por el usuario: {seleccion}. "
        "Responde específicamente sobre esta selección y no vuelvas a solicitarla."
    )

def detectar_aclaracion_tecnica(mensaje: str) -> dict[str, str] | None:
    """Devuelve una aclaración concreta o None si la consulta puede continuar.

    Casos cubiertos:
    - procedimiento de bomba sin identificar CMP-01/CMP-02/CMP-03, o bomba auxiliar sin identificar A/B;
    - verificación de sensor de temperatura sin identificar sensor/circuito;
    - anomalía de temperatura sin identificar circuito;
    - testigo rojo sin código TES;
    - calefacción averiada con petición de sustitución sin diagnóstico;
    - mantenimiento genérico sin elemento o intervención.

    Una consulta sobre un atributo de una bomba singular también requiere aclaración
    cuando el usuario no identifica CMP-01, CMP-02 o CMP-03. Si pide comparar las
    bombas o pregunta explícitamente por todas, puede responderse con los valores de cada una.
    """
    original = (mensaje or "").strip()
    texto = normalizar(original)
    if not texto:
        return None

    tiene_cmp = _tiene_codigo(_PATRON_CMP, original)
    tiene_tes = _tiene_codigo(_PATRON_TES, original)
    tiene_circuito = _tiene_circuito(original)

    # 1. Bombas: distinguir entre una bomba auxiliar genérica (A/B) y una
    # referencia genérica a «la bomba» (CMP-01/CMP-02/CMP-03).
    es_bomba = bool(re.search(r"\bbombas?\b", texto))
    es_bomba_auxiliar = "bomba auxiliar" in texto or "bombas auxiliares" in texto
    pide_procedimiento = _contiene_alguno(texto, _INTENCION_PROCEDIMIENTO)
    pide_dato_bomba_singular = (
        _contiene_alguno(texto, _INTENCION_DATO_BOMBA)
        and bool(re.search(r"\bbomba\b", texto))
        and not bool(re.search(r"\bbombas\b", texto))
    )
    pide_aclaracion_bomba = pide_procedimiento or pide_dato_bomba_singular

    codigos_cmp_detectados = {int(numero) for numero in _PATRON_CMP.findall(original)}
    codigos_cir_detectados = {int(numero) for numero in _PATRON_CIR.findall(original)}
    identifica_bomba_auxiliar = (
        bool(codigos_cmp_detectados.intersection({2, 3}))
        or bool(codigos_cir_detectados.intersection({2, 3}))
        or bool(re.search(r"\bbomba\s+auxiliar\s+[ab]\b", texto))
        or _contiene_alguno(texto, ("circuito de bateria", "circuito bateria",
                                    "electronica de potencia", "circuito de electronica"))
    )
    identifica_bomba_concreta = (
        bool(codigos_cmp_detectados.intersection({1, 2, 3}))
        or bool(codigos_cir_detectados)
        or _contiene_alguno(texto, (
            "bomba mecanica", "bomba del motor", "bomba de motor",
            "bomba de bateria", "bomba del inversor",
            "bomba de electronica de potencia", "bomba del circuito de bateria",
            "bomba del circuito de electronica de potencia",
        ))
    )

    if es_bomba_auxiliar and pide_aclaracion_bomba and not identifica_bomba_auxiliar:
        return {
            "code": "pump_variant",
            "message": (
                "¿A cuál te refieres: a la bomba auxiliar A (CMP-02), que trabaja en "
                "el circuito de batería CIR-02, o a la bomba auxiliar B (CMP-03), "
                "del circuito de electrónica de potencia CIR-03?"
            ),
        }

    if es_bomba and pide_aclaracion_bomba and not es_bomba_auxiliar and not identifica_bomba_concreta:
        return {
            "code": "pump_variant",
            "message": (
                "¿A cuál bomba te refieres: CMP-01 (bomba mecánica del circuito del motor, "
                "CIR-01), CMP-02 (bomba auxiliar A del circuito de batería, CIR-02) "
                "o CMP-03 (bomba auxiliar B del circuito de electrónica de potencia, CIR-03)?"
            ),
        }

    # 2. Sensor de temperatura: el procedimiento PRC-007 abarca varios sensores.
    es_sensor_temperatura = (
        "sensor" in texto
        and _contiene_alguno(texto, ("temperatura", "termico", "termica"))
    )
    identifica_sensor = (
        tiene_cmp
        or tiene_circuito
        or _contiene_alguno(texto, ("sensor del motor", "sensor de bateria",
                                    "sensor de la bateria", "sensor del inversor",
                                    "sensor ambiente", "temperatura ambiente"))
    )
    if es_sensor_temperatura and pide_procedimiento and not identifica_sensor:
        return {
            "code": "temperature_sensor",
            "message": (
                "¿Qué sensor quieres comprobar: el de temperatura del motor (CMP-14), "
                "los sensores de batería (CMP-15), el del inversor (CMP-16) o el "
                "sensor de temperatura ambiente (CMP-20)?"
            ),
        }

    # 3. Temperatura fuera de rango sin circuito identificado.
    anomalia_temperatura = (
        _contiene_alguno(texto, ("temperatura", "temperaturas"))
        and _contiene_alguno(texto, ("fuera de rango", "fuera del rango", "anomala",
                                     "anormal", "demasiado alta", "elevada", "no es normal"))
    )
    identifica_sistema_termico = (
        tiene_cmp
        or tiene_tes
        or tiene_circuito
        or _contiene_alguno(texto, ("motor", "bateria", "inversor", "electronica de potencia"))
    )
    if anomalia_temperatura and not identifica_sistema_termico:
        return {
            "code": "thermal_circuit",
            "message": (
                "¿En qué circuito aparece la temperatura fuera de rango: CIR-01 (motor), "
                "CIR-02 (batería) o CIR-03 (electrónica de potencia)? Si aparece algún "
                "testigo o código HTM, indícamelo también."
            ),
        }

    # 4. Testigo rojo genérico. La documentación distingue TES-01 rojo parpadeante
    # y TES-05; no se debe inferir cuál es sin el código o símbolo.
    testigo_rojo = _contiene_alguno(texto, ("testigo rojo", "luz roja", "aviso rojo",
                                             "indicador rojo"))
    if testigo_rojo and not tiene_tes:
        return {
            "code": "red_indicator",
            "message": (
                "Necesito identificar el testigo antes de indicarte qué hacer. "
                "¿Qué código aparece: TES-01 (temperatura del motor), TES-02 "
                "(temperatura de la batería) o TES-05 (alta tensión/aislamiento)? "
                "Si es TES-01 o TES-02, indica también si está amarillo fijo o rojo "
                "parpadeante. Como precaución, si el testigo está rojo, detente en "
                "un lugar seguro antes de continuar. TES-01 rojo parpadeante exige "
                "detención inmediata; TES-05 siempre exige detención segura y "
                "contacto con personal habilitado en alta tensión."
            ),
        }

    # 5. Calefacción sin diagnóstico. No se recomienda sustituir una pieza solo
    # por un síntoma genérico.
    problema_calefaccion = (
        _contiene_alguno(texto, ("calefaccion", "calentador ptc", "ptc"))
        and _contiene_alguno(texto, ("no funciona", "no calienta", "no calentar",
                                     "no sale calor", "calienta poco", "averiada",
                                     "que componente", "que pieza", "sustituir", "cambiar"))
    )
    tiene_diagnostico = tiene_cmp or tiene_tes or bool(re.search(r"HTM[- ]?\d{4}", original, re.I))
    if problema_calefaccion and not tiene_diagnostico:
        return {
            "code": "heating_diagnosis",
            "message": (
                "No debo recomendar la sustitución de una pieza solo por el síntoma. "
                "Para orientar el diagnóstico 4.6 de calefacción insuficiente, dime: "
                "¿ocurre solo con frío extremo o también con temperaturas moderadas? "
                "¿El problema es reciente o ha empeorado progresivamente? Indica "
                "también si aparece algún testigo o código de avería."
            ),
        }

    # 6. Mantenimiento genérico sin elemento ni intervención.
    pregunta_mantenimiento = _contiene_alguno(
        texto, ("mantenimiento", "revision periodica", "revision general", "servicio periodico")
    ) and _contiene_alguno(texto, ("cada cuanto", "con que frecuencia", "intervalo", "cuando toca"))
    identifica_objeto_mantenimiento = (
        tiene_cmp
        or tiene_tes
        or tiene_circuito
        or _contiene_alguno(texto, ("refrigerante", "filtro", "bomba", "bateria",
                                    "motor", "circuito", "electroventilador", "valvula"))
    )
    if pregunta_mantenimiento and not identifica_objeto_mantenimiento:
        return {
            "code": "maintenance_target",
            "message": (
                "¿De qué elemento o intervención necesitas conocer el intervalo de "
                "mantenimiento: refrigerante, filtro del circuito de batería CMP-24, "
                "bomba auxiliar A/B o electroventilador CMP-09? También puedes indicar "
                "otra operación concreta."
            ),
        }

    return None


def respuesta_aclaracion_tecnica(
    aclaracion: dict[str, str],
    alertas_seguridad: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Construye una respuesta API de aclaración técnica sin llamar al LLM."""
    return respuesta_aclaracion("technical", aclaracion["message"], alertas_seguridad)
