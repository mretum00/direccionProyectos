"""
Lo que devuelve la API al frontend.

- separar_cierre: separa del texto del LLM los pasos seguidos y los fragmentos
  que dice haber utilizado.
- fragmentos_utilizados: se queda solo con los fragmentos de los que el LLM ha
  sacado la información (no todos los recuperados).
- construir_fuentes: convierte los fragmentos usados en fuentes (formato
  `Source` de models/schemas.py).
- respuesta_sin_evidencia: respuesta fija cuando no hay documentación que
  respalde una respuesta. No llama al LLM.
- pedir_aclaracion: pide al usuario que elija la versión del motor cuando falta
  o no existe. No llama al LLM. Solo pide la versión: el perfil siempre llega.
"""

import re
import uuid

from config import ENGINE_VERSIONS, settings

from .prompts import SECCION_FRAGMENTOS, SECCION_PASOS
from .retrieval import documento_de


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


# Guiones que salen de los PDF o del LLM ("HTM240‑BOL‑006"): todos valen como "-".
_GUION = r"[-‐-―−]"
_CODIGO_DOCUMENTO = re.compile(rf"HTM240{_GUION}([A-Z]{{3}}){_GUION}(\d{{3}})")


def codigo_documento(documento: str) -> str:
    """Código de un documento: "HTM240-HIS-001_Casos_servicio.pdf" -> "HTM240-HIS-001".

    Si el nombre no sigue el formato, se devuelve tal cual.
    """
    codigo = _CODIGO_DOCUMENTO.match(documento)
    return f"HTM240-{codigo.group(1)}-{codigo.group(2)}" if codigo else documento


def tipo_documento(documento: str) -> str:
    """Tipo de fuente del contrato según el código del documento (manual si no se reconoce)."""
    codigo = _CODIGO_DOCUMENTO.match(documento)
    return TIPOS_POR_CODIGO.get(codigo.group(1), "manual") if codigo else "manual"


def construir_fuentes(fragmentos: list[dict], version: str) -> list[dict]:
    """Convierte cada fragmento en una fuente con el formato de `Source` (schemas.py)."""
    fuentes = []
    for f in fragmentos:
        chunk_id = f["chunk_id"]
        documento = documento_de(chunk_id)
        codigo = codigo_documento(documento)

        # Sección: código del documento y, en los casos de servicio, el código del caso.
        partes_seccion = [codigo] if codigo != documento else []
        if f.get("seccion"):
            partes_seccion.append(f["seccion"])

        fuentes.append({
            "id": chunk_id,
            "document": documento,
            "source_type": tipo_documento(documento),
            "section": " · ".join(partes_seccion) or None,
            # Página del PDF donde empieza el fragmento (None se omite en la respuesta).
            "page": f.get("pagina"),
            # Versiones a las que aplica el fragmento, no la elegida por el usuario.
            "engine_version": ", ".join(f.get("versiones") or [version]),
            "excerpt": _extracto(f["texto"], settings.source_excerpt_chars),
        })
    return fuentes


_ENCABEZADO = re.compile(r"^\s*#{1,6}\s*\**\s*(.+?)\s*\**\s*:?\s*$")
_VINETA = re.compile(r"^\s*(?:\d+\s*[.)]|[-*•])\s*")


def separar_cierre(texto: str) -> tuple[str, list[str], list[int] | None]:
    """Separa del texto del LLM las secciones de cierre que pide el prompt.

    Devuelve (contenido, pasos, numeros_fragmentos):
      - contenido: la respuesta sin "### PASOS SEGUIDOS" ni "### FRAGMENTOS UTILIZADOS".
      - pasos: cada paso del razonamiento, sin la numeración.
      - numeros_fragmentos: los números de "F1, F3" -> [1, 3]; [] si escribió "Ninguno"
        y None si el LLM no añadió la sección (así se sabe que hay que deducirlos).
    """
    lineas_contenido: list[str] = []
    lineas_pasos: list[str] = []
    lineas_fragmentos: list[str] = []
    destino = lineas_contenido
    hay_fragmentos = False

    for linea in texto.split("\n"):
        encabezado = _ENCABEZADO.match(linea)
        if encabezado:
            titulo = encabezado.group(1).upper()
            if titulo.startswith(SECCION_PASOS):
                destino = lineas_pasos
                continue
            if titulo.startswith(SECCION_FRAGMENTOS):
                destino, hay_fragmentos = lineas_fragmentos, True
                continue
            # Cualquier otro encabezado vuelve a ser parte de la respuesta.
            destino = lineas_contenido
        destino.append(linea)

    pasos = [_VINETA.sub("", linea).strip() for linea in lineas_pasos]
    pasos = [paso for paso in pasos if paso]

    numeros = None
    if hay_fragmentos:
        numeros = [int(n) for n in re.findall(r"\bF\s*(\d+)\b", " ".join(lineas_fragmentos), re.IGNORECASE)]

    return "\n".join(lineas_contenido).strip(), pasos, numeros


# "(F1, F3)" -> "F1, F3": la cita del documento ya se entiende sin paréntesis.
_REFS_ENTRE_PARENTESIS = re.compile(r"\(\s*(F\d+(?:\s*(?:,|;|y|e)\s*F\d+)*)\s*\)")
# Una referencia F1, con el nombre del documento que el LLM escribe a veces delante
# ("HTM240-DIA-001_Manual.pdf F1") o el código detrás ("F1 (BOL-003)"): sobran.
_REFERENCIA = re.compile(
    rf"(?:(HTM240{_GUION}[A-Z]{{3}}{_GUION}\d{{3}}[\w.]*)\s+)?"
    r"\bF(\d+)\b"
    rf"(?:\s*\((?:HTM240{_GUION}?)?[A-Z]{{3}}{_GUION}?\d{{3}}\))?"
)


def cita_fragmento(f: dict) -> str:
    """Cómo se cita un fragmento al usuario: "HTM240-BOL-006 · pág. 3"."""
    codigo = codigo_documento(documento_de(f["chunk_id"]))
    return f"{codigo} · pág. {f['pagina']}" if f.get("pagina") is not None else codigo


def _ids_a_referencias(texto: str, fragmentos: list[dict]) -> str:
    """Si el LLM copia el id interno de un fragmento ("HTM240-DIA-001_Manual.pdf_1"), pasa a "F1"."""
    texto = normalizar_codigos(texto)
    # Los ids más largos primero y sin dígito detrás: "..._pdf_1" no debe comerse "..._pdf_10".
    for numero, f in sorted(enumerate(fragmentos, start=1), key=lambda par: -len(par[1].get("chunk_id", ""))):
        if f.get("chunk_id"):
            texto = re.sub(re.escape(f["chunk_id"]) + r"(?!\d)", f"F{numero}", texto)
    return texto


def citar_fragmentos(texto: str, fragmentos: list[dict]) -> str:
    """Cambia las referencias internas del prompt (F1, F2...) por el documento que citan.

    "Consulté F2" -> "Consulté HTM240-BOL-006 · pág. 3". Al usuario "F2" no le dice nada.
    """
    def _cita(coincidencia: re.Match) -> str:
        delante, numero = coincidencia.group(1), int(coincidencia.group(2))
        if not 1 <= numero <= len(fragmentos):
            return coincidencia.group(0)
        f = fragmentos[numero - 1]
        cita = cita_fragmento(f)
        # Si el documento escrito delante es otro distinto, se conserva.
        if delante and codigo_documento(delante) != codigo_documento(documento_de(f["chunk_id"])):
            return f"{delante} {cita}"
        return cita

    texto = _REFS_ENTRE_PARENTESIS.sub(lambda m: m.group(1), _ids_a_referencias(texto, fragmentos))
    return _REFERENCIA.sub(_cita, texto)


def normalizar_codigos(texto: str) -> str:
    """Guiones raros dentro de códigos ("HTM240‑DIA‑001", "TES‑01") -> guion normal."""
    return re.sub(r"(?<=[A-Z0-9])[‐-‒−](?=[A-Z0-9])", "-", texto)


def extraer_referencias(texto: str, fragmentos: list[dict]) -> tuple[str, list[str]]:
    """Saca de un paso del LLM sus referencias (F1, F2...) para mostrarlas aparte.

    "Revisé la tabla de HTM240-ADV-001 (F2)." -> ("Revisé la tabla de HTM240-ADV-001.",
    ["HTM240-ADV-001 · pág. 2"]). Si el LLM escribió el nombre del fichero delante
    de la referencia, se deja su código en el texto para que la frase siga teniendo sentido.
    """
    citas: list[str] = []

    def _quitar(coincidencia: re.Match) -> str:
        delante, numero = coincidencia.group(1), int(coincidencia.group(2))
        if not 1 <= numero <= len(fragmentos):
            return coincidencia.group(0)
        f = fragmentos[numero - 1]
        cita = cita_fragmento(f)
        if cita not in citas:
            citas.append(cita)
        if delante:
            return codigo_documento(delante)
        # Al final de la frase o entre paréntesis sobra; en medio ("Consulté F2 para...")
        # se deja el código del documento para que la frase siga leyéndose bien.
        resto = coincidencia.string[coincidencia.end():].lstrip()
        fin = not resto or re.match(r"[.,;:)]|(?:y|e)\s+F\d", resto)
        return "" if fin else codigo_documento(documento_de(f["chunk_id"]))

    texto = _REFERENCIA.sub(_quitar, _ids_a_referencias(texto, fragmentos))
    # Restos de quitar las referencias: "()", "(X, )", " ,", "  ", " .", "en." / "según,".
    texto = re.sub(r"\(\s*(?:[,;]|y|e)?\s*\)", "", texto)
    texto = re.sub(r"\s+(?:en|de|del|según|segun|con|y)(?=\s*(?:[,.;:)]|$))", "", texto)
    texto = re.sub(r"\s*[,;]\s*\)", ")", texto)
    texto = re.sub(r"\(\s*[,;]\s*", "(", texto)
    texto = re.sub(r"\s+([,.;:)])", r"\1", texto)
    texto = re.sub(r"\s{2,}", " ", texto).strip()
    return texto, citas


def fragmentos_utilizados(fragmentos: list[dict], numeros: list[int] | None, contenido: str) -> list[dict]:
    """Se queda solo con los fragmentos de los que el LLM ha sacado la información.

    - Si el LLM indicó los fragmentos (F1, F3...), se usan esos (ignorando números
      que no existan o repetidos), en el orden en que se recuperaron.
    - Si no añadió la sección, se usan los fragmentos de los documentos que cita
      en el texto (HTM240-BOL-006...). Si no cita ninguno, no hay fuentes.
    """
    if numeros is not None:
        elegidos = set(numeros)
        return [f for i, f in enumerate(fragmentos, start=1) if i in elegidos]

    citados = {f"HTM240-{tipo}-{numero}" for tipo, numero in _CODIGO_DOCUMENTO.findall(contenido)}
    return [f for f in fragmentos if codigo_documento(documento_de(f["chunk_id"])) in citados]


def respuesta_sin_evidencia(pasos: list[dict] | None = None) -> dict:
    """Respuesta fija cuando no hay documentación que respalde una respuesta."""
    return {
        "steps": pasos or None,
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


def pedir_aclaracion(version_recibida: str) -> dict:
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

    return {
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": texto,
        },
        "needs_clarification": True,
        "sources": [],
        "documents_consulted": 0,
    }