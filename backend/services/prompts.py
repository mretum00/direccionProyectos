"""
Prompts: construcción del texto que se le manda al LLM.

- formatear_historial: convierte el historial del chat en texto para meterlo en
  un prompt, recortando las respuestas largas.
- construir_prompt: junta las reglas del asistente, el perfil del usuario, el
  historial, los fragmentos recuperados y la pregunta en el prompt final.
"""

import re
from typing import Optional

from .retrieval import documento_de

# Secciones finales que el LLM debe añadir siempre. respuestas.py las separa del
# texto: los pasos van al campo `steps` y los fragmentos filtran las fuentes.
SECCION_PASOS = "PASOS SEGUIDOS"
SECCION_FRAGMENTOS = "FRAGMENTOS UTILIZADOS"


def referencia_fragmento(numero: int) -> str:
    """Referencia corta de un fragmento en el prompt: 1 -> "F1"."""
    return f"F{numero}"


def formatear_historial(historial: list[dict], max_chars: int = 500) -> str:
    """Convierte el historial en texto para meterlo en un prompt.

    Las respuestas del asistente son largas (6 secciones), así que se recortan
    para no inflar el prompt. Si el mensaje trae la versión con la que se hizo,
    se indica ("Usuario [V1.0]: ..."): puede haber cambiado dentro del chat.
    """
    lineas = []
    for h in historial:
        # Cada mensaje del frontend trae "role" ("user" o "assistant") y "content".
        quien = "Usuario" if h["role"] == "user" else "Asistente"
        if h.get("engine_version"):
            quien += f" [{h['engine_version']}]"
        texto = h["content"].strip()
        # Recorte: evita que una respuesta larga del asistente ocupe medio prompt.
        if len(texto) > max_chars:
            texto = texto[:max_chars] + "..."
        lineas.append(f"{quien}: {texto}")
    # Un mensaje por línea: "Usuario: ...\nAsistente: ...".
    return "\n".join(lineas)


def construir_prompt(
    mensaje_original: str,
    fragmentos: list[dict],
    perfil: str,
    historial: Optional[list[dict]] = None,
    version: Optional[str] = None,
) -> str:
    """Arma el prompt final: reglas + perfil + historial + fragmentos + pregunta.

    `perfil` es "user" (conductor) o "mechanic" (técnico) y cambia el tono de la
    respuesta. Se usa el mensaje original del usuario, no la consulta traducida.
    """
    # 1. Contexto documental: cada fragmento recuperado se convierte en un bloque
    #    de texto con una cabecera que lo identifica, para que el LLM pueda citarlo.
    #    Se usa .get con valor por defecto para que un fragmento incompleto no rompa el prompt.
    #    Cada fragmento lleva una referencia corta (F1, F2...) que el LLM usa en
    #    "### FRAGMENTOS UTILIZADOS" para indicar de cuáles ha sacado la información
    #    (los chunk_id son largos y el modelo los copiaría mal).
    bloques_contexto = []
    for numero, f in enumerate(fragmentos, start=1):
        chunk_id = f.get("chunk_id", "Desconocido")
        documento = documento_de(chunk_id)
        categoria = f.get("categoria", "Manual")
        versiones = ", ".join(f.get("versiones", [])) if f.get("versiones") else "Todas"
        pagina = f.get("pagina")
        seccion = f.get("seccion")
        texto = f.get("texto", "")

        # Sección y página son opcionales: solo se añaden a la cabecera si existen.
        info_extra = []
        if seccion:
            info_extra.append(f"Sección: {seccion}")
        if pagina is not None:
            info_extra.append(f"Página: {pagina}")
        extra_str = " | " + " | ".join(info_extra) if info_extra else ""

        # Documento como "HTM240-DIA-001 (Manual diagnostico)" en vez del nombre del fichero:
        # el chunk_id y el ".pdf" no se ponen para que el LLM no los copie al citar.
        nombre = re.match(r"(HTM240-[A-Z]{3}-\d{3})_?(.*?)(?:\.pdf)?$", documento)
        if nombre:
            titulo = nombre.group(2).replace("_", " ").strip()
            documento = f"{nombre.group(1)} ({titulo})" if titulo else nombre.group(1)

        # Cabecera entre corchetes (referencia, documento, categoría, versiones...) y debajo el texto.
        bloques_contexto.append(
            f"[{referencia_fragmento(numero)} | Documento: {documento} | Categoría: {categoria} | Versiones aplicables: {versiones}{extra_str}]\n{texto}"
        )

    # Los bloques se separan con una línea "---" para que el LLM vea dónde acaba cada fragmento.
    contexto_unido = "\n\n---\n\n".join(bloques_contexto)

    # 2. Perfil del usuario: cambia el tono y el nivel técnico de la respuesta.
    #    "user" = conductor (lenguaje claro y prudente); cualquier otro valor se trata como mecánico.
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

    # 3. Historial: solo se incluye si hay mensajes previos, para que el LLM entienda
    #    preguntas de seguimiento. Si está vacío, no deja ni una línea en el prompt.
    bloque_historial = (
        f"\nHISTORIAL RECIENTE DE LA CONVERSACIÓN:\n{formatear_historial(historial)}\n"
        if historial
        else ""
    )
    version_seleccionada = version or "No especificada"

    # 4. Prompt final. Orden del texto (NO escribir comentarios Python dentro de las
    #    comillas: se enviarían al LLM):
    #      - perfil del usuario y versión elegida en la interfaz
    #      - historial reciente (si lo hay)
    #      - reglas críticas: fidelidad a los documentos, datos obsoletos, versión del
    #        vehículo (la elegida en la interfaz, sin volver a pedirla),
    #        componentes ambiguos, seguridad y fuera de alcance
    #      - estructura de la respuesta (### RESUMEN y secciones en Markdown)
    #      - cierre obligatorio: pasos seguidos y fragmentos utilizados (F1, F2...)
    #      - contexto documental recuperado y, al final, la pregunta del usuario
    prompt_final = f"""Eres el asistente técnico oficial del sistema de gestión térmica híbrida ThermoDrive HTM-240.

ADAPTACIÓN AL PERFIL:
{instruccion_perfil}

VERSIÓN SELECCIONADA EN LA INTERFAZ: {version_seleccionada}
{bloque_historial}
REGLAS CRÍTICAS DE PRECISIÓN, VERSIONES Y OBSOLESCENCIA (OBLIGATORIAS):
1. FIDELIDAD Y CERO CÓDIGOS INVENTADOS: Responde SOLO con los datos del CONTEXTO DOCUMENTAL. Está TERMINANTEMENTE PROHIBIDO inventar datos, pares de apriete, resistencias o escribir referencias ficticias con signos de interrogación como "HTM240-PRC-??". Cita siempre el código real del documento, sección y página (ej. HTM240-CAT-001, HTM240-DIA-001, HTM240-BOL-006). Si no hay datos para responder, incluye exactamente la frase "No hay evidencia suficiente en la documentación".
2. DATOS OBSOLETOS Y JERARQUÍA DOCUMENTAL (Boletín > Manual vigente > Manual obsoleto):
   - Da siempre como respuesta principal el dato VIGENTE indicando en qué documento y edición se aplica.
   - ADICIONALMENTE, si en el contexto aparece un valor anterior u obsoleto o un boletín que corrige un documento (ej. HTM240-BOL-006 corrige los 80.000 km / 60 meses de HTM240-MNT-001 v1.0 a 60.000 km / 48 meses en v1.1; o HTM240-BOL-002 actualiza PRC-003 a v2.0), DEBES MENCIONAR EXPRESAMENTE qué dato está obsoleto, a qué edición antigua del documento pertenecía y qué boletín/edición contiene el dato correcto vigente.
3. VERSIÓN DEL VEHÍCULO (V1.0, V1.1 y V2.0):
   - La versión del vehículo del usuario es la SELECCIONADA EN LA INTERFAZ: {version_seleccionada}. Ya la conoces: NUNCA pidas al usuario que confirme o indique su versión. Si dice "mi versión", "mi vehículo" o no menciona ninguna, se refiere a {version_seleccionada}.
   - Responde directamente con el dato que aplica a {version_seleccionada} (ej. corriente nominal de la bomba CMP-02: 3-5 A en V1.0 vs. 3-6 A en V1.1/V2.0 según HTM240-BOL-002; código HTM-0142: precalentamiento no completado en V1.x vs. fallo del sensor combinado CMP-18 en V2.0 según HTM240-BOL-003). El contexto documental ya está filtrado: solo contiene documentos aplicables a {version_seleccionada}.
   - NO confundas la edición de un documento con la versión del vehículo: "HTM240-MNT-001 v1.0" o "v1.1" son ediciones del manual, no las versiones V1.0/V1.1 del vehículo. El dato vigente de un documento (su última edición o el boletín que lo corrige) es el que aplica, salvo que el propio documento lo limite a otras versiones del vehículo.
   - En el HISTORIAL cada mensaje indica entre corchetes la versión con la que se hizo. Si es distinta de {version_seleccionada}, el usuario ha cambiado de versión: NO reutilices los datos de esas respuestas, responde solo con el CONTEXTO DOCUMENTAL actual. Si en el historial el asistente pidió confirmar la versión, ignóralo: la versión es {version_seleccionada}.
   - Solo si el usuario pregunta expresamente por otra versión del vehículo distinta de {version_seleccionada}, indica que la respuesta se basa en la documentación de {version_seleccionada} y que cambie la versión seleccionada en la interfaz para consultar la otra.
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
- Empieza SIEMPRE con un encabezado `### RESUMEN` seguido de 1 o 2 frases cortas (unas 35 palabras como máximo) que den lo esencial: la conclusión o respuesta directa y, si aplica, lo más urgente. No uses viñetas, no cites códigos de procedimientos ni documentos y no repitas el detalle de las secciones siguientes (eso va después).
- Después del resumen, desarrolla la respuesta con encabezados en Markdown (cada uno en su propia línea, con este nombre exacto y en este orden):
### CAUSAS POSIBLES
### CRITICIDAD
### SEGURIDAD
### COMPROBACIONES
### PROCEDIMIENTO
### FUENTE
- En consultas de diagnóstico, averías, testigos, códigos DTC o procedimientos, usa las secciones que tengan contenido real en el contexto documental.
- En consultas directas simples (ej. preguntar solo qué función tiene un componente, qué herramienta usa un paso o cada cuántos km se cambia el fluido) o consultas fuera de alcance/ambiguas, usa `### RESUMEN` con la respuesta directa, completa y concisa, añade solo las secciones que realmente aporten (`### SEGURIDAD` si aplica) y cita la `### FUENTE`.
- En ningún caso inventes pasos de desmontaje que nadie ha pedido ni rellenes secciones vacías con "No consta en la documentación recuperada": si una sección no tiene contenido, omítela.

CIERRE OBLIGATORIO (siempre, después de todo lo anterior, con estos dos encabezados exactos):
### {SECCION_PASOS}
- Lista numerada (1., 2., 3....) de entre 3 y 6 pasos que expliquen cómo has llegado a la respuesta. Cada paso es UNA frase (máximo 30 palabras) y debe ser ESPECÍFICO:
  · nombra el dato concreto que has tomado o comprobado (código DTC, testigo, componente, valor numérico con su unidad, umbral, intervalo, versión, nivel de criticidad o habilitación);
  · indica de qué fragmento sale ÚNICAMENTE con su referencia entre paréntesis al final de la frase (ej. "(F2)" o "(F1, F3)"); no escribas nombres de fichero ni códigos de documento en los pasos, la referencia basta;
  · si has elegido un dato frente a otro (vigente frente a obsoleto, una versión frente a otra, seguridad primero), di cuál, frente a cuál y por qué;
  · si has descartado algún fragmento recuperado por no ser relevante para la pregunta, añade un paso diciendo cuál y por qué (todos aplican a la versión {version_seleccionada}: no los descartes por la versión).
  Forma de un paso válido (rellénalo con datos reales del contexto, no copies los marcadores): "El testigo TES-XX aparece asociado al código HTM-XXXX (condición y valor que lo activa), con criticidad <nivel> (F2)."
  Ejemplo NO válido (demasiado genérico): "Consulté la documentación para ver las comprobaciones recomendadas."
  Describe solo lo que has hecho de verdad; no inventes pasos ni datos.
### {SECCION_FRAGMENTOS}
- Una sola línea con las referencias (F1, F2...) de los fragmentos de los que has sacado información que aparece en la respuesta, separadas por comas (ej. "F1, F3"). No incluyas fragmentos recuperados que no hayas usado. Si no has usado ninguno, escribe "Ninguno".

CONTEXTO DOCUMENTAL RECUPERADO:
{contexto_unido}

CONSULTA DEL USUARIO:
{mensaje_original}
"""
    return prompt_final