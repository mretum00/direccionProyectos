"""
Genera la base de datos vectorial (SQLite) a partir de los manuales.

Ejecutar desde cualquier directorio (la BD se crea siempre desde cero):
    python backend/db/database_generator.py

Toda la configuración (rutas, modelo de embeddings, tamaño de fragmento) sale de
las variables de entorno definidas en backend/config.py, de modo que el modelo
usado aquí es siempre el mismo que usa el backend al responder.

Qué hace, en orden:
  1. Lee cada PDF, quita ruido (cabecera de página, aviso "uso educativo", guiones
     de fin de línea que partían palabras y códigos como "HTM- 0142").
  2. Detecta la estructura (apartados "4.1 ...", entradas "HTM-0142", casos de servicio)
     y trocea SIN cruzar de un apartado a otro, para poder citar la sección.
  3. Asigna a cada fragmento las versiones del motor a las que aplica, su página y su sección.
  4. Calcula los embeddings por lotes y los guarda en la BD, que se crea desde cero.
  5. Verifica la BD (versiones válidas, vectores, totales declarados por los PDF...).
     Si hay errores la elimina, para que el backend nunca sirva datos incompletos.
"""

import bisect
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ENGINE_VERSIONS, settings  # noqa: E402
from db.models import RagChunk  # noqa: E402
from db.repositories import RagChunkRepository  # noqa: E402

# La consola de Windows puede no ser UTF-8: evita que un acento rompa la ingesta.
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# CONFIGURACIÓN
# ============================================================

DB_PATH = settings.db_path
BASE_DIR = settings.manuals_dir
MODEL_NAME = settings.embedding_model

CHUNK_SIZE = settings.rag_chunk_size
CHUNK_OVERLAP = settings.rag_chunk_overlap

# Un fragmento más corto que esto no aporta nada a la búsqueda.
MIN_CARACTERES_FRAGMENTO = 40

FORMATOS_SOPORTADOS = (".pdf", ".txt", ".md")

# Recopilatorio con todos los documentos juntos: duplica los fragmentos y,
# como sus versiones no se pueden deducir por el nombre, rompe el filtro por versión.
ARCHIVOS_EXCLUIDOS = {"HTM240_Documentacion_Completa_Alumnos.pdf"}

CARPETA_SUSTITUIDOS = "00_Documentos_sustituidos"

# Versiones del motor a las que aplica cada documento cuando NO son todas. La fuente es el
# propio documento ("Versiones afectadas" en los boletines, "Aplicabilidad" en los procedimientos);
# todo documento que no esté aquí vale para ENGINE_VERSIONS. Si se añade un documento que
# aplica solo a algunas versiones, hay que añadirlo aquí: no se deduce del texto de sus fragmentos.
VERSIONES_POR_DOCUMENTO = {
    "HTM240-BOL-001": ["V1.0"],           # "V1.0 (no aplica a V1.1 ni V2.0)"
    "HTM240-BOL-002": ["V1.1", "V2.0"],   # "V1.1 y posteriores (V2.0 incluido)"
    "HTM240-BOL-004": ["V1.0", "V1.1"],   # "V1.0 y V1.1 con relé CMP-25 de lote anterior a 2025-05"
    "HTM240-BOL-005": ["V2.0"],           # "V2.0 (referencia ST-B200); no retrocompatible con V1.x"
    "HTM240-BOL-007": ["V2.0"],           # "Únicamente V2.0 (PTC de 5 kW)"
    "HTM240-PRC-003": ["V1.1", "V2.0"],   # versión 2.0 vigente: "V1.1 y V2.0. Para V1.0 ver la versión previa"
}

# Documentos de la carpeta de sustituidos que SE INDEXAN porque siguen siendo la referencia
# válida para alguna versión (código -> versiones). El resto de sustituidos se ignoran: su
# contenido es erróneo u obsoleto para todas las versiones (p. ej. MNT-001 v1.0 y sus 80.000 km).
SUSTITUIDOS_INDEXADOS = {
    "HTM240-PRC-003": ["V1.0"],           # "Aplicable únicamente, con carácter histórico, a V1.0"
}

# Primera línea de todas las páginas de los PDF: es ruido y se elimina.
CABECERA_PAGINA = "ThermoDrive HTM-240 — Documentacion sintetica para uso educativo"

# Aviso "documentación sintética para uso educativo" que abre cada documento. Es el mismo
# en todos y ensucia el primer fragmento; el backend ya lo recuerda en el prompt.
PATRON_AVISO = re.compile(
    r"DOCUMENTACI[OÓ]N SINT[EÉ]TICA PARA USO EDUCATIVO\..*?veh[ií]culos\s+reales\.",
    re.DOTALL,
)

# Prefijos de código: "HTM-\n0142" es un código partido por el salto de línea, no una palabra.
PREFIJOS_CODIGO = {
    "HTM", "CMP", "TES", "CIR", "ST", "TOOL",
    "PRC", "BOL", "DIA", "DTC", "CAT", "SEG", "MAN", "OPE", "MNT", "ADV", "ESQ", "HIS", "DIC",
    "POST",   # "post-parada" es una palabra compuesta real
}
PATRON_GUION_FIN_LINEA = re.compile(r"(\w+)-[ \t]*\n[ \t]*(\S)")

# Entradas de los catálogos: "CMP-01 — Bomba mecanica..." y "HTM-0142 — Estrategia...".
PATRON_ENTRADA = re.compile(r"^(CMP-\d{2}|HTM-\d{4}) — ")
# Cabecera de cada caso de servicio: "HTM-CASO-016 — 2025-10-11 (V1.0, 19900 km)".
# Grupo 1 = código del caso, grupo 2 = versión del vehículo del caso.
PATRON_CASO = re.compile(r"^(HTM-CASO-\d{3}) — [^()]*\((V\d\.\d)")
# Apartados numerados de los manuales: "4.1 Sobrecalentamiento del motor", "1. Objetivo del sistema".
# Máx. 70 caracteres y sin punto: así no se confunden con los pasos de un procedimiento ("1. Verificar ...").
PATRON_APARTADO = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-ZÁÉÍÓÚ][^.]{2,70}$")

# Los procedimientos usan encabezados sin numerar; se reconocen como secciones reales.
SECCIONES_PRC = {
    "Objetivo",
    "Aplicabilidad",
    "Perfil autorizado",
    "Riesgos",
    "Equipos de protección individual",
    "Herramientas necesarias",
    "Condiciones previas",
    "Pasos",
    "Valores esperados",
    "Criterios de aceptación",
    "Acción si el resultado no es correcto",
    "Verificación final",
    "Documentos relacionados",
}

# Los boletines actuales organizan su contenido bajo este encabezado.
SECCIONES_BOL = {"Contenido", "Referencias"}

# Datos del encabezado de cada documento que se usan para comprobar versiones y totales.
PATRON_APLICABLE = re.compile(r"Aplicable a:\s*(?:HTM-240\s*)?(V\d\.\d(?:\s*,\s*V\d\.\d)*)")
PATRON_APLICABILIDAD = re.compile(r"Aplicabilidad\s+(Todas las versiones|V\d\.\d(?:\s*(?:,|y)\s*V\d\.\d)*)")
PATRON_TOTAL = re.compile(r"Total de (?:componentes|códigos|casos|términos):\s*(\d+)")
PATRON_CODIGO_DOC = re.compile(r"^(HTM240-([A-Z]{3})-\d{3})")

_embedder = None


def obtener_embedder():
    """Carga el modelo de embeddings la primera vez que se necesita (tarda varios segundos)."""
    global _embedder

    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        print("Cargando modelo de embeddings...")
        _embedder = SentenceTransformer(MODEL_NAME)

    return _embedder


# ============================================================
# MODELO DE DATOS
# ============================================================

@dataclass
class Documento:
    """Un archivo ya leído y limpio, listo para trocear."""

    archivo: str
    codigo: Optional[str]            # "HTM240-PRC-003"
    tipo: Optional[str]              # "PRC", "DTC", "HIS"... (3 letras del código)
    categoria: str
    sustituido: bool
    versiones: list[str]             # versiones a las que aplica el documento
    lineas: list[str]                # texto limpio, una línea por elemento
    texto: str                       # las mismas líneas en un solo texto
    inicios_pagina: list[int]        # inicios_pagina[i] = posición donde empieza la página i+1
    apartados: list[tuple[int, str, Optional[list[str]]]]  # (posición, etiqueta, versiones propias)
    avisos: list[str] = field(default_factory=list)            # algo raro que conviene revisar
    comprobaciones: list[str] = field(default_factory=list)    # comprobaciones superadas


# ============================================================
# BASE DE DATOS
# ============================================================

# El esquema de la tabla (rag_documents: chunk_id, text, category, applicable_versions, embedding,
# page, section) está en db/models.py; el acceso a ella, en el repositorio.
repositorio = RagChunkRepository()


# ============================================================
# EXTRACCIÓN Y LIMPIEZA DE TEXTO
# ============================================================

def _unir_guion(coincidencia):
    palabra, siguiente = coincidencia.group(1), coincidencia.group(2)

    # Código partido ("HTM-" + "0142", "ST-" + "B100"): se conserva el guion.
    if siguiente.isdigit() or palabra.upper() in PREFIJOS_CODIGO or any(c.isdigit() for c in palabra):
        return f"{palabra}-{siguiente}"

    # Palabra partida ("temper-" + "atura"): se junta sin guion.
    return f"{palabra}{siguiente}"


def limpiar_pagina(texto):
    """Líneas limpias de una página: sin cabecera, número de página, aviso ni guiones de fin de línea."""
    lineas = texto.strip().split("\n")

    if lineas and lineas[0].strip() == CABECERA_PAGINA:
        lineas = lineas[1:]
    if lineas and lineas[-1].strip().isdigit():
        lineas = lineas[:-1]

    texto = PATRON_GUION_FIN_LINEA.sub(_unir_guion, "\n".join(lineas))
    texto = PATRON_AVISO.sub("", texto)

    return [re.sub(r"\s+", " ", linea).strip() for linea in texto.split("\n") if linea.strip()]


def extraer_paginas_pdf(ruta_pdf):
    """Líneas limpias de cada página del PDF. Lanza la excepción si el PDF no se puede leer."""
    with pymupdf.open(ruta_pdf) as documento:
        return [limpiar_pagina(pagina.get_text("text")) for pagina in documento]


def extraer_paginas_archivo(ruta_completa):
    """Lista con las líneas de cada página. Un .txt/.md cuenta como una sola página."""
    extension = os.path.splitext(ruta_completa)[1].lower()

    if extension == ".pdf":
        return extraer_paginas_pdf(ruta_completa)

    with open(ruta_completa, "r", encoding="utf-8") as archivo:
        return [limpiar_pagina(archivo.read())]


# ============================================================
# ESTRUCTURA DEL DOCUMENTO
# ============================================================

def detectar_apartado(linea, tipo):
    """Si la línea abre un apartado, devuelve (etiqueta, versiones propias); si no, None."""
    if tipo in ("CAT", "DTC"):
        coincidencia = PATRON_ENTRADA.match(linea)
        return (coincidencia.group(1), None) if coincidencia else None

    if tipo == "HIS":
        coincidencia = PATRON_CASO.match(linea)
        return (coincidencia.group(1), [coincidencia.group(2)]) if coincidencia else None

    if tipo == "PRC" and linea in SECCIONES_PRC:
        return (linea, None)

    if tipo == "BOL" and linea in SECCIONES_BOL:
        return (linea, None)

    if tipo in (None, "DIC"):
        return None

    if PATRON_APARTADO.match(linea):
        return (linea[:90], None)

    return None


def construir_texto(paginas, tipo):
    """Junta las páginas en un solo texto y recuerda dónde empieza cada página y cada apartado."""
    partes = []
    inicios_pagina = []
    apartados = []
    posicion = 0
    inicio_subsistema = None

    for lineas in paginas:
        inicios_pagina.append(posicion)

        for linea in lineas:
            # En el catálogo DTC, "Subsistema: ..." va entre dos entradas y describe las de DESPUÉS:
            # se pega al principio de la siguiente entrada, no al final de la anterior.
            if tipo == "DTC" and linea.startswith("Subsistema:"):
                inicio_subsistema = posicion

            apartado = detectar_apartado(linea, tipo)
            if apartado:
                apartados.append((posicion if inicio_subsistema is None else inicio_subsistema, apartado[0], apartado[1]))
                inicio_subsistema = None

            partes.append(linea)
            posicion += len(linea) + 1   # +1 por el espacio que las separa

    return " ".join(partes), inicios_pagina, apartados


def pagina_de(posicion, inicios):
    """Número de página (empezando en 1) en la que cae una posición del texto."""
    return bisect.bisect_right(inicios, posicion)


# ============================================================
# DATOS DEL DOCUMENTO: VERSIONES, CATEGORÍA Y ENCABEZADO
# ============================================================

def versiones_en_orden(conjunto):
    return [v for v in ENGINE_VERSIONS if v in conjunto]


def determinar_versiones(codigo, sustituido):
    """Versiones del motor a las que aplica el documento entero (None si hay que ignorarlo)."""
    if sustituido:
        versiones = SUSTITUIDOS_INDEXADOS.get(codigo)
        return list(versiones) if versiones else None

    return list(VERSIONES_POR_DOCUMENTO.get(codigo, ENGINE_VERSIONS))


def determinar_categoria(nombre_carpeta):
    if "Diccionario" in nombre_carpeta:
        return "Dictionary"

    elif "Codigos_DTC" in nombre_carpeta:
        return "DTC"

    return "Manual"


def versiones_declaradas(texto_cabecera):
    """Versiones que el encabezado del documento dice cubrir, o None si no lo dice de forma clara."""
    coincidencia = PATRON_APLICABLE.search(texto_cabecera) or PATRON_APLICABILIDAD.search(texto_cabecera)
    if not coincidencia:
        return None

    declarado = coincidencia.group(1)
    if declarado.startswith("Todas"):
        return set(ENGINE_VERSIONS)

    return set(re.findall(r"V\d\.\d", declarado))


def cargar_documento(ruta_completa, archivo, categoria, sustituido):
    """Lee y limpia un archivo. Devuelve None si no hay que indexarlo (sustituido sin interés)."""
    coincidencia = PATRON_CODIGO_DOC.match(archivo)
    codigo = coincidencia.group(1) if coincidencia else None
    tipo = coincidencia.group(2) if coincidencia else None

    versiones = determinar_versiones(codigo, sustituido)
    if versiones is None:
        return None

    paginas = extraer_paginas_archivo(ruta_completa)
    texto, inicios_pagina, apartados = construir_texto(paginas, tipo)

    documento = Documento(
        archivo=archivo,
        codigo=codigo,
        tipo=tipo,
        categoria=categoria,
        sustituido=sustituido,
        versiones=versiones,
        lineas=[linea for lineas in paginas for linea in lineas],
        texto=texto,
        inicios_pagina=inicios_pagina,
        apartados=apartados,
    )

    cabecera = texto[:900]

    # Comprobación cruzada: lo que dice el encabezado frente a lo que hemos asignado.
    declaradas = versiones_declaradas(cabecera)
    if declaradas is not None and not sustituido and declaradas != set(versiones):
        documento.avisos.append(
            f"el encabezado declara {versiones_en_orden(declaradas)} pero se asignó {versiones}. "
            "Revisa VERSIONES_POR_DOCUMENTO."
        )

    return documento


# ============================================================
# TROCEADO DE DOCUMENTOS
# ============================================================
# Cada función es un generador que produce diccionarios con "id", "texto", "contexto"
# (prefijo que solo se usa para calcular el embedding) y opcionalmente "inicio",
# "seccion" y "versiones": así no se guardan todos los fragmentos en memoria.

def procesar_diccionario(documento):
    """Un fragmento por viñeta, conservando el término y su posición dentro del PDF."""
    # `documento.texto` usa el mismo espacio entre líneas que `inicios_pagina`, por lo que
    # la posición de cada viñeta se puede convertir directamente en número de página.
    indice = 0

    for term in re.finditer(r"•\s*(.*?)(?=\s•|\Z)", documento.texto, re.DOTALL):
        termino = re.sub(r"\s+", " ", term.group(1)).strip()

        if len(termino) > 10:
            etiqueta = termino.split(":", 1)[0].strip()
            yield {
                "id": f"{documento.archivo}_DIC{indice}",
                "texto": f"Expresión coloquial/Término: {termino}",
                "contexto": "",
                "inicio": term.start(),
                "seccion": etiqueta or f"Término {indice + 1}",
            }

            indice += 1


def _punto_de_corte(texto, inicio, fin, chunk_size):
    """Dónde cortar un fragmento que no cabe: mejor al final de una frase, si no en un espacio."""
    minimo = inicio + int(chunk_size * 0.6)

    punto = texto.rfind(". ", minimo, fin)
    if punto != -1:
        return punto + 1

    espacio = texto.rfind(" ", inicio, fin)
    return espacio if espacio > inicio else fin


def ventanas(texto, desde, hasta, chunk_size, overlap):
    """Trocea texto[desde:hasta] en ventanas de ~`chunk_size` caracteres con solapamiento.

    Devuelve (posición donde empieza el fragmento, fragmento).
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap debe ser mayor o igual que cero y menor que chunk_size")

    inicio = desde

    while inicio < hasta:
        fin = min(inicio + chunk_size, hasta)

        if fin < hasta:
            fin = _punto_de_corte(texto, inicio, fin, chunk_size)

        bruto = texto[inicio:fin]
        fragmento = bruto.strip()

        if len(fragmento) >= MIN_CARACTERES_FRAGMENTO:
            yield inicio + len(bruto) - len(bruto.lstrip()), fragmento

        if fin >= hasta:
            break

        # Avanzamos manteniendo el solapamiento, pero empezando en una palabra completa.
        nuevo_inicio = fin - overlap
        espacio = texto.find(" ", nuevo_inicio, fin)
        if espacio != -1:
            nuevo_inicio = espacio + 1

        # Si así no avanzara (bucle infinito), seguimos desde `fin`.
        inicio = nuevo_inicio if nuevo_inicio > inicio else fin


def procesar_documento_tecnico(documento, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Trocea por apartados: un fragmento nunca mezcla el final de un apartado con el principio del siguiente."""
    texto = documento.texto

    # Tramos (desde, hasta, etiqueta, versiones): lo anterior al primer apartado y cada apartado.
    limites = [posicion for posicion, _, _ in documento.apartados] + [len(texto)]
    tramos = []

    if not documento.apartados or documento.apartados[0][0] > 0:
        tramos.append((0, limites[0], None, None))

    for i, (posicion, etiqueta, versiones) in enumerate(documento.apartados):
        tramos.append((posicion, limites[i + 1], etiqueta, versiones))

    indice = 0

    for desde, hasta, etiqueta, versiones in tramos:
        for inicio, fragmento in ventanas(texto, desde, hasta, chunk_size, overlap):
            # El tramo anterior al primer encabezado es información introductoria del documento.
            # Se etiqueta explícitamente para que no llegue una fuente sin sección al frontend.
            seccion = etiqueta or "Introducción"
            chunk = {
                "id": f"{documento.archivo}_{indice}",
                "texto": fragmento,
                # Si el fragmento no empieza por el título del apartado (es la 2.ª ventana en
                # adelante), el título se añade solo al calcular el embedding. Así un fragmento
                # del medio de "HTM-0142" sigue sabiendo de qué código habla.
                "contexto": f"{seccion}. " if etiqueta and inicio > desde else "",
                "inicio": inicio,
                "seccion": seccion,
            }
            if versiones:
                chunk["versiones"] = versiones

            yield chunk
            indice += 1


def trocear(documento):
    """Elige cómo trocear el documento según su tipo."""
    if documento.categoria == "Dictionary":
        # El diccionario se separa por viñetas, que necesitan los saltos de línea.
        return procesar_diccionario(documento)

    return procesar_documento_tecnico(documento)


# ============================================================
# INGESTA DE DOCUMENTOS
# ============================================================

def entradas_detectadas(documento, fragmentos):
    """Cuántas entradas (códigos, casos, términos) tiene el documento, para compararlas con su 'Total de ...'."""
    if documento.categoria == "Dictionary":
        return len(fragmentos)

    return len({etiqueta for _, etiqueta, _ in documento.apartados}) if documento.tipo in ("CAT", "DTC", "HIS") else None


def indexar_documento(documento):
    """Trocea un documento, calcula sus embeddings y lo guarda. Devuelve cuántos fragmentos insertó."""
    fragmentos = list(trocear(documento))

    if not fragmentos:
        return 0

    # Los embeddings se calculan por lotes: mucho más rápido que de uno en uno.
    vectores = obtener_embedder().encode(
        [f["contexto"] + f["texto"] for f in fragmentos],
        batch_size=32,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True
    ).astype(np.float32)

    filas = []
    for fragmento, vector in zip(fragmentos, vectores):
        # Los casos de servicio traen su propia versión; el resto, la del documento.
        versiones = fragmento.get("versiones") or documento.versiones

        # Página en la que empieza el fragmento (el diccionario no la tiene).
        pagina = pagina_de(fragmento["inicio"], documento.inicios_pagina) if "inicio" in fragmento else None

        filas.append(RagChunk(
            chunk_id=fragmento["id"],
            text=fragmento["texto"],
            category=documento.categoria,
            applicable_versions=json.dumps(versiones),
            embedding=vector.tobytes(),
            page=pagina,
            section=fragmento.get("seccion"),
        ))

    # Todo el documento o nada: si algo falla, no queda a medias.
    repositorio.add_many(filas)

    # El PDF declara cuántas entradas tiene ("Total de códigos: 36"): si no coinciden, falta o sobra algo.
    declarado = PATRON_TOTAL.search(documento.texto[:900])
    encontradas = entradas_detectadas(documento, fragmentos)

    if declarado and encontradas is not None:
        if int(declarado.group(1)) == encontradas:
            documento.comprobaciones.append(f"declara {encontradas} entradas y se han detectado {encontradas}")
        else:
            documento.avisos.append(
                f"el documento declara {declarado.group(1)} entradas y se han detectado {encontradas}"
            )

    return len(fragmentos)


# ============================================================
# VERIFICACIÓN DE LA BD GENERADA
# ============================================================

def verificar_bd():
    """Comprueba que la BD es coherente. Devuelve (errores, avisos)."""
    errores = []
    avisos = []

    filas = repositorio.list_all()

    if not filas:
        return ["La BD no tiene ningún fragmento."], avisos

    modelo = obtener_embedder()
    # Tamaño de un vector del modelo, en bytes (float32). Se mide con un texto de prueba en vez de preguntarlo al
    # modelo, porque el método que lo da cambia de nombre entre versiones de sentence-transformers.
    bytes_esperados = len(modelo.encode("prueba", convert_to_numpy=True)) * 4

    por_version = {v: 0 for v in ENGINE_VERSIONS}

    for fila in filas:
        # Los campos de Peewee son opcionales: un valor vacío se trata como dato inválido, no como un fallo del código.
        chunk_id, categoria, embedding, pagina = fila.chunk_id, fila.category, fila.embedding or b"", fila.page
        versiones = json.loads(fila.applicable_versions or "[]")
        desconocidas = [v for v in versiones if v not in ENGINE_VERSIONS]

        if not versiones or desconocidas:
            errores.append(f"{chunk_id}: versiones no válidas {versiones} (válidas: {list(ENGINE_VERSIONS)})")

        if len(embedding) != bytes_esperados:
            errores.append(f"{chunk_id}: el embedding no tiene el tamaño del modelo")
        elif abs(float(np.linalg.norm(np.frombuffer(embedding, dtype=np.float32))) - 1.0) > 1e-3:
            errores.append(f"{chunk_id}: el embedding no está normalizado")

        # Los documentos sustituidos llevan SUSTITUIDO en el nombre: nunca valen para todas las versiones.
        if "SUSTITUIDO" in chunk_id and set(versiones) == set(ENGINE_VERSIONS):
            errores.append(f"{chunk_id}: documento sustituido válido para todas las versiones")

        if pagina is None:
            avisos.append(f"{chunk_id}: sin número de página")

        if not fila.section or not fila.section.strip():
            avisos.append(f"{chunk_id}: sin sección identificada")

        if categoria != "Dictionary":
            for v in versiones:
                if v in por_version:
                    por_version[v] += 1

    for version, total in por_version.items():
        if total == 0:
            errores.append(f"Ningún fragmento aplica a {version}: el selector de versión no devolvería nada.")

    return errores, avisos


# ============================================================
# INGESTA
# ============================================================

def listar_archivos():
    """Todos los archivos indexables, en orden estable: (ruta, nombre, carpeta, sustituido)."""
    for raiz, carpetas, archivos in os.walk(BASE_DIR):
        carpetas.sort()
        sustituido = CARPETA_SUSTITUIDOS in os.path.relpath(raiz, BASE_DIR).split(os.sep)
        categoria = determinar_categoria(os.path.basename(raiz))

        for archivo in sorted(archivos):
            # Solo formatos soportados; el recopilatorio completo se ignora.
            if not archivo.lower().endswith(FORMATOS_SOPORTADOS) or archivo in ARCHIVOS_EXCLUIDOS:
                continue

            yield os.path.join(raiz, archivo), archivo, categoria, sustituido


def ejecutar_ingesta():
    if not os.path.isdir(BASE_DIR):
        print(f"[!] No existe el directorio: {BASE_DIR}")
        return 1

    try:
        repositorio.recreate()
    except PermissionError:
        print(f"[!] No se puede borrar {DB_PATH}: otro proceso la tiene abierta (¿el backend?). Páralo y vuelve a ejecutar.")
        return 1

    resumen = []                 # (archivo, fragmentos, versiones, estado)
    documentos_con_error = []
    total_fragmentos = 0
    interrumpida = False

    print("\nIniciando escaneo de documentos...")

    try:
        for ruta, archivo, categoria, sustituido in listar_archivos():
            print(f"\nProcesando: {archivo}")

            try:
                documento = cargar_documento(ruta, archivo, categoria, sustituido)

                if documento is None:
                    print("[-] Documento sustituido sin vigencia para ninguna versión: se ignora.")
                    continue

                fragmentos = indexar_documento(documento)

            except Exception as e:
                documentos_con_error.append(archivo)
                print(f"[!] Error procesando {archivo}: {e}")
                continue

            if fragmentos == 0:
                documentos_con_error.append(archivo)
                print(f"[!] No se generaron fragmentos: {archivo}")
                continue

            total_fragmentos += fragmentos
            resumen.append((documento, fragmentos))
            print(f"[+] Procesado: {archivo} -> {fragmentos} fragmentos, versiones {documento.versiones}.")

            for comprobacion in documento.comprobaciones:
                print(f"[=] {comprobacion}")

            for aviso in documento.avisos:
                print(f"[?] {archivo}: {aviso}")

    except KeyboardInterrupt:
        interrumpida = True
        print("\n[!] Ingesta interrumpida por el usuario.")

    if interrumpida:
        repositorio.delete_database()
        print("Se elimina la BD incompleta.")
        return 1

    print("\nVerificando la BD...")
    errores, avisos = verificar_bd()

    # --- Informe ---
    print("\n" + "=" * 50)
    print("RESUMEN DE LA INGESTA")
    print("=" * 50)
    print(f"Documentos procesados: {len(resumen)}")
    print(f"Fragmentos insertados: {total_fragmentos}")
    print(f"Documentos con error: {len(documentos_con_error)}")
    print(f"Troceado: {CHUNK_SIZE} caracteres, solapamiento {CHUNK_OVERLAP}")

    restringidos = [(d, n) for d, n in resumen if set(d.versiones) != set(ENGINE_VERSIONS)]
    if restringidos:
        print("\nDocumentos que NO aplican a todas las versiones:")
        for documento, fragmentos in restringidos:
            print(f"  {documento.archivo[:60]:60} {documento.versiones}")

    for aviso in avisos[:10]:
        print(f"[?] {aviso}")
    if len(avisos) > 10:
        print(f"[?] ... y {len(avisos) - 10} avisos más")

    for archivo in documentos_con_error:
        errores.append(f"Documento sin indexar: {archivo}")

    if errores:
        for error in errores:
            print(f"[ERROR] {error}")
        # Una BD con errores no se deja: el backend no debe servir datos incompletos.
        repositorio.delete_database()
        print("\nLa BD tiene errores y se ha eliminado. Corrígelos y vuelve a ejecutar el generador.")
        return 1

    print(f"\nBD generada en {DB_PATH}")
    return 0


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

if __name__ == "__main__":
    sys.exit(ejecutar_ingesta())
