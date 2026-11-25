"""Normalización de texto compartida por las comprobaciones de citas y la salida del LLM.

El modelo (gpt-oss) escribe a menudo guiones y espacios tipográficos: "CMP‑02" con un
guion no separable (U+2011) o "100 %" con un espacio fino (U+202F). Los documentos usan
el guion y el espacio normales, así que sin normalizar una cita copiada "literalmente"
no se encontraba en el fragmento y R07 la daba por no concluyente.
"""

import re
import unicodedata

# Todas las variantes de guion y signo menos -> "-".
_GUIONES = re.compile(r"[‐-―−﹘﹣－]")
# Comillas tipográficas -> comillas rectas.
_COMILLAS_DOBLES = re.compile(r"[“”„«»]")
_COMILLAS_SIMPLES = re.compile(r"[‘’‚]")


def normalizar_cita(texto: str) -> str:
    """Forma canónica para comparar una cita con el texto de un fragmento.

    Unicode NFKC, minúsculas, un solo tipo de guion y de comillas y espacios
    colapsados. Se aplica a los dos lados de la comparación. Además quita las
    comillas y puntos suspensivos de los extremos: el modelo suele devolver la cita
    entre comillas ('"Forzar la activación..."') y eso no forma parte del documento.
    """
    texto = unicodedata.normalize("NFKC", texto or "")
    texto = _GUIONES.sub("-", texto)
    texto = _COMILLAS_DOBLES.sub('"', texto)
    texto = _COMILLAS_SIMPLES.sub("'", texto)
    texto = " ".join(texto.casefold().split())
    return texto.strip(" \"'.…")


# Solo los guiones que el modelo pone dentro de códigos y palabras (U+2010, U+2011):
# las rayas y semirrayas de la prosa ("—", "–") se respetan.
_GUIONES_DE_PALABRA = re.compile(r"[‐‑]")
_ESPACIOS_ESPECIALES = re.compile(r"[   ]")


def limpiar_salida_llm(texto: str) -> str:
    """Sustituye guiones y espacios tipográficos del modelo por los normales.

    Así "CMP‑02" se escribe igual que en los documentos: se reconoce como código en
    la interfaz, en la búsqueda y en las comprobaciones de citas.
    """
    return _ESPACIOS_ESPECIALES.sub(" ", _GUIONES_DE_PALABRA.sub("-", texto or ""))


def quitar_comillas(cita: str) -> str:
    """Cita sin las comillas con las que el modelo la envuelve: '"Forzar..."' -> 'Forzar...'."""
    return (cita or "").strip().strip("\"'“”«»‘’").strip()


_ELIPSIS = re.compile(r"\s*(?:\.\.\.|…|\[\s*\.\.\.\s*\]|\(\s*\.\.\.\s*\))\s*")


def cita_en_texto(cita: str, texto: str) -> bool:
    """¿Aparece la cita en el texto del fragmento?

    Compara las formas normalizadas. Si el modelo abrevia la cita con puntos
    suspensivos ("Consultar el caudal ... (debe ser 0 l/min)"), cada trozo debe
    aparecer en el fragmento y en el mismo orden; los trozos muy cortos no cuentan
    como evidencia para no aceptar citas hechas solo de "..." y una palabra.
    """
    texto_normalizado = normalizar_cita(texto)
    trozos = [normalizar_cita(trozo) for trozo in _ELIPSIS.split(cita or "")]
    trozos = [trozo for trozo in trozos if trozo]
    if not trozos or sum(len(trozo) for trozo in trozos) < 12:
        return False
    posicion = 0
    for trozo in trozos:
        encontrado = texto_normalizado.find(trozo, posicion)
        if encontrado < 0:
            return False
        posicion = encontrado + len(trozo)
    return True


def localizar_cita(cita: str, fragmentos: list[dict], preferidos: list[dict]) -> list[str]:
    """chunk_id de los fragmentos que contienen la cita.

    Primero se busca en los fragmentos que indicó el modelo. Si la cita no está en
    ninguno pero sí, literalmente, en otro fragmento del mismo contexto, se acepta ese:
    el modelo a veces copia bien la cita y numera mal la referencia (F2 en vez de F1).
    Sigue exigiéndose una cita literal de lo que el modelo recibió. Si todas sus
    referencias eran inventadas (F99), no se busca en otros: se rechaza.
    """
    if not cita or not preferidos:
        return []
    for candidatos in (preferidos, fragmentos):
        ids = [
            str(fragmento.get("chunk_id"))
            for fragmento in candidatos
            if fragmento.get("chunk_id") and cita_en_texto(cita, str(fragmento.get("texto", "")))
        ]
        if ids:
            return list(dict.fromkeys(ids))
    return []
