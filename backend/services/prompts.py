"""
Prompts: construcción del texto que se le manda al LLM.

- formatear_historial: convierte el historial del chat en texto para meterlo en
  un prompt, recortando las respuestas largas.
- construir_prompt: junta las reglas del asistente, el perfil del usuario, el
  historial, los fragmentos recuperados y la pregunta en el prompt final.
"""

from typing import Optional

from .retrieval import documento_de


def formatear_historial(historial: list[dict], max_chars: int = 500) -> str:
    """Convierte el historial en texto para meterlo en un prompt.

    Las respuestas del asistente son largas (6 secciones), así que se recortan
    para no inflar el prompt.
    """
    lineas = []
    for h in historial:
        # Cada mensaje del frontend trae "role" ("user" o "assistant") y "content".
        quien = "Usuario" if h["role"] == "user" else "Asistente"
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
    instruccion_suficiencia: Optional[str] = None,
) -> str:
    """Arma el prompt final: reglas + perfil + historial + fragmentos + pregunta.

    `perfil` es "user" (conductor) o "mechanic" (técnico) y cambia el tono de la
    respuesta. Se usa el mensaje original del usuario, no la consulta traducida.
    """
    # 1. Contexto documental: cada fragmento recuperado se convierte en un bloque
    #    de texto con una cabecera que lo identifica, para que el LLM pueda citarlo.
    #    Se usa .get con valor por defecto para que un fragmento incompleto no rompa el prompt.
    bloques_contexto = []
    for indice, f in enumerate(fragmentos, start=1):
        # Identificador corto y estable dentro de esta respuesta; el backend lo valida
        # contra la lista real de fragmentos antes de mostrarlo como cita.
        referencia = f"[F{indice}]"
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

        # Cabecera entre corchetes (documento, fragmento, categoría, versiones...) y debajo el texto.
        bloques_contexto.append(
            f"{referencia} [Documento: {documento} | Fragmento: {chunk_id} | Categoría: {categoria} | Versiones aplicables: {versiones}{extra_str}]\n{texto}"
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
    bloque_suficiencia = (
        f"\nRESTRICCIÓN DE COBERTURA DOCUMENTAL (R07):\n{instruccion_suficiencia}\n"
        if instruccion_suficiencia
        else ""
    )

    # 4. Prompt final. Orden del texto (NO escribir comentarios Python dentro de las
    #    comillas: se enviarían al LLM):
    #      - perfil del usuario y versión elegida en la interfaz
    #      - historial reciente (si lo hay)
    #      - reglas críticas: fidelidad a los documentos, versiones y datos obsoletos,
    #        componentes ambiguos, seguridad y fuera de alcance
    #      - estructura de la respuesta (### RESUMEN y secciones en Markdown)
    #      - contexto documental recuperado y, al final, la pregunta del usuario
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
7. TRAZABILIDAD DE FUENTES (OBLIGATORIA):
   - Cada fragmento del CONTEXTO DOCUMENTAL tiene un identificador entre corchetes, por ejemplo [F1], [F2].
   - En la sección `### FUENTE`, enumera únicamente los identificadores de los fragmentos que realmente has utilizado como apoyo para redactar la respuesta.
   - Escribe cada referencia con su identificador exacto y, si está disponible, el documento, sección y página. Ejemplo: `- [F1] HTM240-DTC-001, sección HTM-0101, página 1`.
   - SOLO puedes utilizar identificadores que aparezcan en el CONTEXTO DOCUMENTAL. No inventes, modifiques ni deduzcas otros identificadores.
   - Si ningún fragmento respalda directamente la respuesta, no inventes referencias ni incluyas identificadores.

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

{bloque_suficiencia}
CONTEXTO DOCUMENTAL RECUPERADO:
{contexto_unido}

CONSULTA DEL USUARIO:
{mensaje_original}
"""
    return prompt_final