"""
Lo que devuelve la API al frontend.

Todas las respuestas del asistente salen de `nueva_respuesta`, así tienen siempre
los mismos campos (formato `ChatResponse` de models/schemas.py) y el frontend
puede pintarlas igual. Hay tres tipos:

- respuesta normal: texto del LLM con fuentes (la arma rag_pipeline.py).
- aclaración (`respuesta_aclaracion`): la consulta se detiene antes de buscar
  porque falta un dato (versión, componente...). No llama al LLM.
- sin evidencia (`respuesta_sin_evidencia`): la documentación no permite
  responder con fiabilidad. No llama al LLM.

Además:
- construir_fuentes: convierte los fragmentos usados en fuentes (`Source`).
- pedir_aclaracion: aclaración para elegir la versión del motor.
- respuesta_limitada_por_verificacion: recorta la respuesta a lo verificado.
"""

import re
import uuid
from typing import Any, Literal, Optional

from config import ENGINE_VERSIONS, settings

from .suficiencia_evidencia import resultado_suficiencia_no_ejecutada
from .texto import cita_en_texto
from .verificacion import resultado_verificacion_no_ejecutada

TipoAclaracion = Literal["engine_version", "technical", "version_mismatch", "version_comparison"]

TEXTO_SIN_EVIDENCIA = (
    "No hay información suficiente para responder a esta consulta. "
    "Se recomienda escalar la incidencia al equipo de soporte."
)


def nueva_respuesta(
    contenido: str,
    *,
    evidencia: str = "insufficient",
    aclaracion: Optional[TipoAclaracion] = None,
    fuentes: Optional[list[dict]] = None,
    documentos: int = 0,
    alertas: Optional[list[dict]] = None,
    verificacion: Optional[dict] = None,
    suficiencia: Optional[dict] = None,
    pasos: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Única forma de construir una respuesta del asistente (formato ChatResponse).

    Rellena siempre todos los campos, con valores neutros si no aplican, para
    que ninguna rama del flujo devuelva una respuesta con otra forma.
    """
    respuesta: dict[str, Any] = {
        "message": {"id": str(uuid.uuid4()), "role": "assistant", "content": contenido},
        "evidence_status": evidencia,
        "needs_clarification": aclaracion is not None,
        "sources": fuentes or [],
        "documents_consulted": documentos,
        "safety_alerts": alertas or [],
        "claim_verification": verificacion or resultado_verificacion_no_ejecutada(),
        "evidence_sufficiency": suficiencia or resultado_suficiencia_no_ejecutada(),
        "steps": pasos or [],
    }
    if aclaracion is not None:
        respuesta["clarification_kind"] = aclaracion
    return respuesta


def respuesta_aclaracion(
    tipo: TipoAclaracion,
    contenido: str,
    alertas: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """La consulta se detiene para pedir un dato al usuario. No llama al LLM."""
    return nueva_respuesta(contenido, aclaracion=tipo, alertas=alertas)


def respuesta_sin_evidencia(contenido: str = TEXTO_SIN_EVIDENCIA, **campos: Any) -> dict[str, Any]:
    """Respuesta fija cuando no hay documentación que respalde una respuesta.

    `campos` admite los mismos argumentos con nombre que `nueva_respuesta`
    (pasos, alertas, suficiencia...). La evidencia siempre es insuficiente.
    """
    return nueva_respuesta(contenido, evidencia="insufficient", **campos)


def contar_documentos(fragmentos: list[dict]) -> int:
    """Documentos distintos entre los fragmentos ("HTM240-DTC-001_3" -> "HTM240-DTC-001")."""
    return len({
        str(fragmento["chunk_id"]).rsplit("_", 1)[0]
        for fragmento in fragmentos
        if fragmento.get("chunk_id")
    })


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


def extraer_referencias_citadas(texto_respuesta: str, total_fragmentos: int) -> set[int]:
    """Extrae los marcadores [F1], [F2] de la sección FUENTE y valida su rango.

    Los marcadores no se aceptan desde otras partes de la respuesta. Así, una mención
    casual dentro del resumen no convierte por sí sola un fragmento en fuente citada.
    Devuelve índices 1-based que corresponden al orden de fragmentos del prompt.
    """
    seccion = re.search(
        r"(?im)^#{1,6}\s*FUENTES?\s*$([\s\S]*?)(?=^#{1,6}\s+|\Z)",
        texto_respuesta,
    )
    if not seccion:
        return set()

    encontrados = re.findall(r"\[F(\d+)\]", seccion.group(1), flags=re.IGNORECASE)
    return {int(valor) for valor in encontrados if 1 <= int(valor) <= total_fragmentos}


def construir_fuentes(
    fragmentos: list[dict],
    version: str,
    referencias_citadas: set[int] | None = None,
) -> list[dict]:
    """Convierte los fragmentos en fuentes y distingue citas del contexto recuperado.

    `referencias_citadas` contiene índices 1-based validados contra el contexto entregado
    al modelo. Los fragmentos restantes se conservan como contexto recuperado, no como
    referencias declaradas por el asistente.
    """
    from .retrieval import documento_de

    referencias_citadas = referencias_citadas or set()
    fuentes = []
    for indice, f in enumerate(fragmentos, start=1):
        chunk_id = f["chunk_id"]
        documento = documento_de(chunk_id)

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
            "citation_status": "cited" if indice in referencias_citadas else "retrieved",
        })
    return fuentes


def pedir_aclaracion(version_recibida: str, alertas: Optional[list[dict]] = None) -> dict[str, Any]:
    """Pide al usuario que elija la versión del motor. No llama al LLM.

    El frontend, al ver `needs_clarification`, muestra el aviso con el botón
    que abre el selector de motor.
    """
    version_recibida = version_recibida.strip()
    opciones = ", ".join(ENGINE_VERSIONS)

    # Mensaje distinto si la versión venía rellena pero no existe, o si venía vacía.
    if version_recibida:
        texto = (
            f"No reconozco la versión «{version_recibida}». "
            f"¿Me dices cuál tienes? Elige una de estas: {opciones}."
        )
    else:
        texto = (
            "Antes de responderte necesito saber qué versión del motor tienes "
            f"({opciones}). Elígela en el selector de motor."
        )

    return respuesta_aclaracion("engine_version", texto, alertas)



_PATRON_INTERVALO_CAUDAL = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(?:a|[-–—])"
    r"\s*(\d+(?:[.,]\d+)?)\s*(l\s*/\s*min)\b",
    re.IGNORECASE,
)


def normalizar_intervalos_caudal(texto: str) -> str:
    """
    Normaliza los intervalos de caudal expresados en l/min.

    Ejemplos:
        8a14l/min    -> 8-14 l/min
        8 a 14 l/min -> 8-14 l/min
        8–14l/min    -> 8-14 l/min

    No modifica otros valores ni unidades.
    """
    return _PATRON_INTERVALO_CAUDAL.sub(
        lambda coincidencia: (
            f"{coincidencia.group(1)}-"
            f"{coincidencia.group(2)} l/min"
        ),
        texto,
    )

def respuesta_limitada_por_verificacion(
    verificacion: dict,
    fragmentos: list[dict],
) -> tuple[str, set[int]]:
    """Construye una respuesta conservadora solo con afirmaciones verificadas.

    No vuelve a llamar al LLM. Solo conserva afirmaciones ``supported`` que tengan
    una cita literal validada dentro de un fragmento identificado. Devuelve también
    los índices 1-based que deben marcarse como fuentes citadas en la respuesta.
    """
    fragmentos_por_id = {
        str(fragmento.get("chunk_id")): (indice, fragmento)
        for indice, fragmento in enumerate(fragmentos, start=1)
        if fragmento.get("chunk_id")
    }

    afirmaciones_respaldadas: list[tuple[str, str, list[int]]] = []
    for afirmacion in verificacion.get("claims", []):
        if not isinstance(afirmacion, dict) or afirmacion.get("status") != "supported":
            continue

        claim = str(afirmacion.get("claim", "")).strip()
        cita = str(afirmacion.get("evidence_excerpt", "")).strip()
        ids_fuente = afirmacion.get("source_ids", [])
        if not claim or not cita or not isinstance(ids_fuente, list):
            continue

        indices_validos: list[int] = []
        for source_id in ids_fuente:
            localizado = fragmentos_por_id.get(str(source_id))
            if localizado is None:
                continue
            indice, fragmento = localizado
            if cita_en_texto(cita, str(fragmento.get("texto", ""))):
                indices_validos.append(indice)

        if indices_validos:
            # Evita que el modelo introduzca referencias [Fxx] falsas dentro del texto de claim.
            claim = re.sub(r"\s*\[F\d+\]", "", claim).strip()
            afirmaciones_respaldadas.append((claim, cita, sorted(set(indices_validos))))

    total = max(
        int(verificacion.get("claims_total", len(verificacion.get("claims", [])))),
        len(verificacion.get("claims", [])),
    )
    omitidas = max(total - len(afirmaciones_respaldadas), 0)
    referencias: set[int] = set()

    if not afirmaciones_respaldadas:
        texto = (
            "La revisión automática no ha encontrado ninguna afirmación con una cita literal "
            "validada en los fragmentos recuperados. Para evitar presentar información técnica "
            "no comprobada, no se muestra la respuesta generada. Consulta la documentación "
            "original o solicita una revisión al equipo técnico."
        )
        return texto, referencias

    lineas = [
        "La revisión automática ha detectado afirmaciones que no ha podido respaldar por completo. "
        "Para evitar presentar información no confirmada, se muestran únicamente las afirmaciones "
        "con una cita literal validada.",
        "",
        "### Información respaldada",
    ]
    for claim, cita, indices in afirmaciones_respaldadas:
        refs = " ".join(f"[F{indice}]" for indice in indices)
        referencias.update(indices)
        lineas.extend([f"- {claim} {refs}", f"  > {cita}", ""])

    if omitidas:
        lineas.append(
            f"Se han omitido {omitidas} afirmación(es) que no pudieron verificarse "
            "o presentaron posibles contradicciones."
        )

    lineas.extend(["", "### FUENTES"])
    for indice in sorted(referencias):
        fragmento = fragmentos[indice - 1]
        chunk_id = str(fragmento.get("chunk_id", ""))
        documento = chunk_id.rsplit("_", 1)[0] if "_" in chunk_id else chunk_id
        seccion = str(fragmento.get("seccion") or "")
        pagina = fragmento.get("pagina")
        detalle = " · ".join(parte for parte in (documento, seccion) if parte)
        if pagina is not None:
            detalle = f"{detalle} · página {pagina}"
        lineas.append(f"- [F{indice}] {detalle}" if detalle else f"- [F{indice}]")

    return "\n".join(lineas).strip(), referencias
