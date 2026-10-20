"""
Genera la base de datos vectorial (SQLite) a partir de los manuales.

Ejecutar desde cualquier directorio:
    python backend/db/database_generator.py

Toda la configuración (rutas, modelo de embeddings, tamaño de fragmento) sale de
las variables de entorno definidas en backend/config.py, de modo que el modelo
usado aquí es siempre el mismo que usa el backend al responder.
"""

import json
import os
import re
import sqlite3
import sys

import numpy as np
import pymupdf
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings  # noqa: E402


# ============================================================
# CONFIGURACIÓN
# ============================================================

DB_PATH = settings.db_path
BASE_DIR = settings.manuals_dir
MODEL_NAME = settings.embedding_model

CHUNK_SIZE = settings.rag_chunk_size
CHUNK_OVERLAP = settings.rag_chunk_overlap


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

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            chunk_id TEXT PRIMARY KEY,
            text TEXT,
            category TEXT,
            applicable_versions TEXT,
            embedding BLOB
        )
    """)

    conn.commit()

    return conn


# ============================================================
# EXTRACCIÓN DE TEXTO
# ============================================================

def extraer_texto_pdf(ruta_pdf):
    paginas = []

    try:
        with pymupdf.open(ruta_pdf) as documento:
            for pagina in documento:
                paginas.append(pagina.get_text("text"))

    except Exception as e:
        print(f"[!] Error al procesar el PDF {ruta_pdf}: {e}")

    return "\n".join(paginas)


def extraer_texto_archivo(ruta_completa):
    extension = os.path.splitext(ruta_completa)[1].lower()

    if extension == ".pdf":
        return extraer_texto_pdf(ruta_completa)

    if extension in (".txt", ".md"):
        try:
            with open(ruta_completa, "r", encoding="utf-8") as archivo:
                return archivo.read()

        except UnicodeDecodeError:
            print(f"[!] Error de codificación en {ruta_completa}")

        except OSError as e:
            print(f"[!] Error leyendo {ruta_completa}: {e}")

    return ""


# ============================================================
# CLASIFICACIÓN DE VERSIONES Y CATEGORÍAS
# ============================================================

def determinar_versiones(texto, documento_id):
    versiones = ["V1.0", "V1.1", "V2.0"]

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
# PROCESAMIENTO DE DOCUMENTOS
# ============================================================

def procesar_diccionario(texto_completo, id_archivo):
    """
    Genera las entradas del diccionario progresivamente.
    No almacena todos los términos en una lista.
    """

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
    """
    Divide el texto en fragmentos con solapamiento.
    Utiliza yield para no guardar todos los fragmentos en memoria.
    """

    texto_limpio = re.sub(r"\s+", " ", texto_completo).strip()

    longitud = len(texto_limpio)
    inicio = 0
    indice = 0

    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap debe ser mayor o igual que cero "
            "y menor que chunk_size"
        )

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
                "texto": fragmento
            }

            indice += 1

        # Si hemos llegado al final, terminamos.
        if fin >= longitud:
            break

        # Avanzamos manteniendo el solapamiento.
        nuevo_inicio = fin - overlap

        # Protección contra bucles infinitos.
        if nuevo_inicio <= inicio:
            nuevo_inicio = fin

        inicio = nuevo_inicio


# ============================================================
# INGESTA DE DOCUMENTOS
# ============================================================

def ejecutar_ingesta():
    if not os.path.isdir(BASE_DIR):
        print(f"[!] No existe el directorio: {BASE_DIR}")
        return

    conn = inicializar_bd()
    cursor = conn.cursor()

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

            nombre_carpeta = os.path.basename(raiz)
            categoria = determinar_categoria(nombre_carpeta)

            for archivo in archivos:

                if not archivo.lower().endswith(
                    (".pdf", ".txt", ".md")
                ):
                    continue

                ruta_completa = os.path.join(raiz, archivo)

                print(f"\nProcesando: {archivo}")

                try:
                    texto_extraido = extraer_texto_archivo(
                        ruta_completa
                    )

                    if not texto_extraido.strip():
                        print("[!] El documento no contiene texto.")
                        continue

                    if categoria == "Dictionary":
                        chunks = procesar_diccionario(
                            texto_extraido, archivo
                        )
                    else:
                        chunks = procesar_documento_tecnico(
                            texto_extraido, archivo
                        )

                    fragmentos_insertados = 0

                    # Procesar cada fragmento sin crear una lista.
                    for chunk in chunks:

                        texto_chunk = chunk["texto"]

                        if len(texto_chunk) < 20:
                            continue

                        vector = embedder.encode(
                            texto_chunk,
                            convert_to_numpy=True,
                            show_progress_bar=False,
                            normalize_embeddings=True
                        )

                        vector_bytes = vector.astype(
                            np.float32
                        ).tobytes()

                        versiones = determinar_versiones(
                            texto_chunk, chunk["id"]
                        )

                        cursor.execute("""
                            INSERT OR REPLACE INTO rag_documents
                            (
                                chunk_id,
                                text,
                                category,
                                applicable_versions,
                                embedding
                            )
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            chunk["id"],
                            texto_chunk,
                            categoria,
                            versiones,
                            vector_bytes
                        ))

                        fragmentos_insertados += 1

                    # Guardar los resultados de cada documento.
                    conn.commit()

                    if fragmentos_insertados > 0:
                        total_documentos += 1
                        total_fragmentos += fragmentos_insertados

                        print(
                            f"[+] Procesado: {archivo} -> "
                            f"{fragmentos_insertados} fragmentos."
                        )
                    else:
                        print(
                            f"[!] No se generaron fragmentos: {archivo}"
                        )

                except Exception as e:
                    # Conservar los fragmentos insertados antes
                    # del error, si los hubiera.
                    conn.commit()

                    documentos_con_error += 1

                    print(
                        f"[!] Error procesando {archivo}: {e}"
                    )

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
