"""
Genera la base de datos vectorial (SQLite) a partir de los manuales.

Ejecutar desde cualquier directorio:
    python backend/db/database_generator.py

Toda la configuración (rutas, modelo de embeddings, tamaño de fragmento) sale de
las variables de entorno definidas en backend/config.py, de modo que el modelo
usado aquí es siempre el mismo que usa el backend al responder.
"""

import bisect
import json
import os
import re
import sqlite3
import sys

import numpy as np
import pymupdf
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ENGINE_VERSIONS, settings  # noqa: E402


# ============================================================
# CONFIGURACIÓN
# ============================================================

DB_PATH = settings.db_path
BASE_DIR = settings.manuals_dir
MODEL_NAME = settings.embedding_model

CHUNK_SIZE = settings.rag_chunk_size
CHUNK_OVERLAP = settings.rag_chunk_overlap

# Recopilatorio con todos los documentos juntos: duplica los fragmentos y,
# como sus versiones no se pueden deducir por el nombre, rompe el filtro por versión.
ARCHIVOS_EXCLUIDOS = {"HTM240_Documentacion_Completa_Alumnos.pdf"}

# Primera línea de todas las páginas de los PDF: es ruido y se elimina.
CABECERA_PAGINA = "ThermoDrive HTM-240 — Documentacion sintetica para uso educativo"

# Cabecera de cada caso de servicio: "HTM-CASO-016 — 2025-10-11 (V1.0, 19900 km)".
# Grupo 1 = código del caso, grupo 2 = versión del vehículo del caso.
PATRON_CASO = re.compile(r"(HTM-CASO-\d{3}) — [^()]*\((V\d\.\d)")


# ============================================================
# CARGA DEL MODELO
# ============================================================

print("Cargando modelo de embeddings...")
embedder = SentenceTransformer(MODEL_NAME)


# ============================================================
# BASE DE DATOS
# ============================================================

def inicializar_bd():
    conn = sqlite3.connect(DB_PATH)

    # Se regenera siempre desde cero: así no quedan fragmentos antiguos de
    # documentos excluidos o con otro troceado, y las BD de versiones
    # anteriores (sin las columnas page/section) se actualizan solas.
    conn.execute("DROP TABLE IF EXISTS rag_documents")

    conn.execute("""
        CREATE TABLE rag_documents (
            chunk_id TEXT PRIMARY KEY,
            text TEXT,
            category TEXT,
            applicable_versions TEXT,
            embedding BLOB,
            page INTEGER,
            section TEXT
        )
    """)

    conn.commit()

    return conn


# ============================================================
# EXTRACCIÓN DE TEXTO
# ============================================================

def extraer_paginas_pdf(ruta_pdf):
    """Devuelve el texto de cada página por separado (sin cabecera ni número de página)."""
    paginas = []

    try:
        with pymupdf.open(ruta_pdf) as documento:
            for pagina in documento:
                lineas = pagina.get_text("text").strip().split("\n")

                if lineas and lineas[0].strip() == CABECERA_PAGINA:
                    lineas = lineas[1:]
                if lineas and lineas[-1].strip().isdigit():
                    lineas = lineas[:-1]

                paginas.append("\n".join(lineas))

    except Exception as e:
        print(f"[!] Error al procesar el PDF {ruta_pdf}: {e}")

    return paginas


def extraer_paginas_archivo(ruta_completa):
    """Lista con el texto de cada página. Un .txt/.md cuenta como una sola página."""
    extension = os.path.splitext(ruta_completa)[1].lower()

    if extension == ".pdf":
        return extraer_paginas_pdf(ruta_completa)

    if extension in (".txt", ".md"):
        try:
            with open(ruta_completa, "r", encoding="utf-8") as archivo:
                return [archivo.read()]

        except UnicodeDecodeError:
            print(f"[!] Error de codificación en {ruta_completa}")

        except OSError as e:
            print(f"[!] Error leyendo {ruta_completa}: {e}")

    return []


def unir_paginas(paginas):
    """Junta las páginas en un solo texto limpio y recuerda dónde empieza cada una.

    Devuelve (texto, inicios), donde inicios[i] es la posición del texto en la
    que empieza la página i+1. Sirve para saber de qué página sale cada fragmento.
    """
    partes = []
    inicios = []
    posicion = 0

    for pagina in paginas:
        limpio = re.sub(r"\s+", " ", pagina).strip()
        inicios.append(posicion)
        partes.append(limpio)
        posicion += len(limpio) + 1   # +1 por el espacio que las separa

    return " ".join(partes), inicios


def pagina_de(posicion, inicios):
    """Número de página (empezando en 1) en la que cae una posición del texto."""
    return bisect.bisect_right(inicios, posicion)


# ============================================================
# CLASIFICACIÓN DE VERSIONES Y CATEGORÍAS
# ============================================================

def determinar_versiones(texto, documento_id):
    # Por defecto un fragmento vale para todas las versiones; las reglas siguientes lo acotan
    # (son reglas de contenido de estos documentos, no la lista de versiones: esa está en config.py).
    versiones = list(ENGINE_VERSIONS)

    if "HTM240-BOL-001" in documento_id:
        versiones = ["V1.0"]

    elif "HTM240-BOL-002" in documento_id:
        versiones = ["V1.1", "V2.0"]

    elif "ST-B200" in texto or "PTC de 5 kW" in texto:
        versiones = ["V2.0"]

    return json.dumps(versiones)


def determinar_categoria(nombre_carpeta):
    if "Diccionario" in nombre_carpeta:
        return "Dictionary"

    elif "Codigos_DTC" in nombre_carpeta:
        return "DTC"

    return "Manual"


# ============================================================
# TROCEADO DE DOCUMENTOS
# ============================================================
# Cada función es un generador que produce diccionarios con, como mínimo,
# "id" y "texto" (y opcionalmente "inicio", "seccion" y "versiones"): así no se
# guardan todos los fragmentos en memoria.

def procesar_diccionario(texto_completo, id_archivo):
    """Un fragmento por cada viñeta (•) del diccionario."""
    indice = 0

    for term in re.finditer(
        r"(?:^|\n)•\s*(.*?)(?=\n•\s*|\Z)",
        texto_completo,
        re.DOTALL
    ):
        termino = term.group(1).strip()

        if len(termino) > 10:
            yield {
                "id": f"{id_archivo}_DIC_{indice}",
                "texto": f"Expresión coloquial/Término: {termino}"
            }

            indice += 1


def procesar_documento_tecnico(
    texto_completo,
    id_archivo,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):
    """Divide el texto en fragmentos de `chunk_size` caracteres con solapamiento."""

    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap debe ser mayor o igual que cero "
            "y menor que chunk_size"
        )

    texto_limpio = re.sub(r"\s+", " ", texto_completo).strip()

    longitud = len(texto_limpio)
    inicio = 0
    indice = 0

    while inicio < longitud:
        fin = min(inicio + chunk_size, longitud)

        if fin < longitud:
            ultimo_espacio = texto_limpio.rfind(
                " ", inicio, fin
            )

            # Solo ajustamos el final si podemos avanzar.
            if ultimo_espacio > inicio:
                fin = ultimo_espacio

        fragmento = texto_limpio[inicio:fin].strip()

        if len(fragmento) > 20:
            yield {
                "id": f"{id_archivo}_{indice}",
                "texto": fragmento,
                "inicio": inicio,   # para calcular la página
            }

            indice += 1

        # Si hemos llegado al final, terminamos.
        if fin >= longitud:
            break

        # Avanzamos manteniendo el solapamiento; si así no avanzara (bucle infinito), seguimos desde `fin`.
        nuevo_inicio = fin - overlap
        inicio = nuevo_inicio if nuevo_inicio > inicio else fin


def procesar_casos_servicio(texto_limpio, id_archivo):
    """Un fragmento por caso de servicio, con su código y la versión de su vehículo.

    Los casos de distintas versiones están mezclados en el mismo PDF: trocear
    cada 800 caracteres juntaba casos V1.0 y V2.0 en un mismo fragmento y el
    filtro por versión dejaba pasar casos de otra versión.
    """
    cabeceras = list(PATRON_CASO.finditer(texto_limpio))

    if not cabeceras:
        yield from procesar_documento_tecnico(texto_limpio, id_archivo)
        return

    # Introducción del documento (antes del primer caso): troceado normal.
    yield from procesar_documento_tecnico(texto_limpio[:cabeceras[0].start()], id_archivo)

    for i, cabecera in enumerate(cabeceras):
        inicio = cabecera.start()
        fin = cabeceras[i + 1].start() if i + 1 < len(cabeceras) else len(texto_limpio)
        codigo, version = cabecera.group(1), cabecera.group(2)

        yield {
            "id": f"{id_archivo}_{codigo}",
            "texto": texto_limpio[inicio:fin].strip(),
            "inicio": inicio,
            "seccion": codigo,
            "versiones": [version],
        }


def trocear(archivo, categoria, paginas, texto_limpio):
    """Elige cómo trocear el documento según su tipo."""
    if categoria == "Dictionary":
        # El diccionario se separa por viñetas, que necesitan los saltos de línea.
        return procesar_diccionario("\n".join(paginas), archivo)

    if archivo.startswith("HTM240-HIS-"):
        return procesar_casos_servicio(texto_limpio, archivo)

    return procesar_documento_tecnico(texto_limpio, archivo)


# ============================================================
# INGESTA DE DOCUMENTOS
# ============================================================

def indexar_archivo(conn, ruta_completa, archivo, categoria):
    """Trocea un documento, calcula sus embeddings y lo guarda. Devuelve cuántos fragmentos insertó."""
    paginas = extraer_paginas_archivo(ruta_completa)
    texto_limpio, inicios_pagina = unir_paginas(paginas)

    if not texto_limpio:
        return 0

    insertados = 0

    for chunk in trocear(archivo, categoria, paginas, texto_limpio):
        vector = embedder.encode(
            chunk["texto"],
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True
        )

        # Los casos de servicio traen su propia versión; el resto se deduce.
        if "versiones" in chunk:
            versiones = json.dumps(chunk["versiones"])
        else:
            versiones = determinar_versiones(chunk["texto"], chunk["id"])

        # Página en la que empieza el fragmento (el diccionario no la tiene).
        pagina = pagina_de(chunk["inicio"], inicios_pagina) if "inicio" in chunk else None

        conn.execute(
            """
            INSERT OR REPLACE INTO rag_documents
                (chunk_id, text, category, applicable_versions, embedding, page, section)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk["id"],
                chunk["texto"],
                categoria,
                versiones,
                vector.astype(np.float32).tobytes(),
                pagina,
                chunk.get("seccion"),
            ),
        )

        insertados += 1

    return insertados


def ejecutar_ingesta():
    if not os.path.isdir(BASE_DIR):
        print(f"[!] No existe el directorio: {BASE_DIR}")
        return

    conn = inicializar_bd()

    total_documentos = 0
    total_fragmentos = 0
    documentos_con_error = 0

    print("\nIniciando escaneo de documentos...")

    try:
        for raiz, carpetas, archivos in os.walk(BASE_DIR):

            # Ignorar documentos sustituidos.
            carpetas[:] = [
                carpeta for carpeta in carpetas
                if "00_Documentos_sustituidos" not in carpeta
            ]

            categoria = determinar_categoria(os.path.basename(raiz))

            for archivo in archivos:

                # Solo formatos soportados; el recopilatorio completo se ignora.
                if not archivo.lower().endswith((".pdf", ".txt", ".md")):
                    continue

                if archivo in ARCHIVOS_EXCLUIDOS:
                    continue

                print(f"\nProcesando: {archivo}")

                try:
                    fragmentos = indexar_archivo(
                        conn, os.path.join(raiz, archivo), archivo, categoria
                    )
                except Exception as e:
                    documentos_con_error += 1
                    print(f"[!] Error procesando {archivo}: {e}")
                else:
                    if fragmentos > 0:
                        total_documentos += 1
                        total_fragmentos += fragmentos
                        print(f"[+] Procesado: {archivo} -> {fragmentos} fragmentos.")
                    else:
                        print(f"[!] No se generaron fragmentos: {archivo}")
                finally:
                    # Se guarda cada documento, conservando los fragmentos
                    # insertados antes de un posible error.
                    conn.commit()

    except KeyboardInterrupt:
        conn.commit()
        print("\n[!] Ingesta interrumpida por el usuario.")

    finally:
        conn.close()

    print("\n" + "=" * 50)
    print("RESUMEN DE LA INGESTA")
    print("=" * 50)
    print(f"Documentos procesados: {total_documentos}")
    print(f"Fragmentos insertados: {total_fragmentos}")
    print(f"Documentos con error: {documentos_con_error}")
    print("Conexión con la base de datos cerrada.")


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

if __name__ == "__main__":
    ejecutar_ingesta()
