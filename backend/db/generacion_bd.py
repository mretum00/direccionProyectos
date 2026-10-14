import os
import sqlite3
import json
import re
import numpy as np
import fitz  # Librería PyMuPDF para leer los PDF nativamente
from sentence_transformers import SentenceTransformer

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
DB_PATH = "thermodrive_rag.db"
# IMPORTANTE: Cambia esta ruta por la ruta real donde tienes las carpetas extraídas
BASE_DIR = "./manual_htm240" 
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2" # Modelo asimétrico optimizado para RAG

print("Cargando modelo de embeddings (esto puede tardar unos segundos la primera vez)...")
embedder = SentenceTransformer(MODEL_NAME)


# ==========================================
# 2. FUNCIONES DE BASE DE DATOS Y LECTURA
# ==========================================
def inicializar_bd():
    """Crea la base de datos SQLite y la tabla de vectores/metadatos"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documentos_rag (
            id_fragmento TEXT PRIMARY KEY,
            texto TEXT,
            categoria TEXT,
            versiones_aplicables TEXT, -- Guardado como JSON string
            embedding BLOB -- Vector matemático guardado como datos binarios
        )
    ''')
    conn.commit()
    return conn

def extraer_texto_pdf(ruta_pdf):
    """Extrae el texto de un PDF página por página usando PyMuPDF"""
    texto = ""
    try:
        documento = fitz.open(ruta_pdf)
        for pagina in documento:
            texto += pagina.get_text("text") + "\n"
        documento.close()
    except Exception as e:
        print(f"Error al procesar el PDF {ruta_pdf}: {e}")
    return texto


# ==========================================
# 3. EXTRACCIÓN DE METADATOS
# ==========================================
def determinar_versiones(texto, documento_id):
    """Asigna las etiquetas de versión correspondientes para el filtrado posterior"""
    versiones = ["V1.0", "V1.1", "V2.0"]
    
    if "HTM240-BOL-001" in documento_id:
        versiones = ["V1.0"]
    elif "HTM240-BOL-002" in documento_id:
        versiones = ["V1.1", "V2.0"]
    elif "ST-B200" in texto or "PTC de 5 kW" in texto:
        versiones = ["V2.0"]
        
    return json.dumps(versiones)

def determinar_categoria(nombre_carpeta):
    """Clasifica el fragmento según su carpeta de origen"""
    if "Diccionario" in nombre_carpeta:
        return "Diccionario"
    elif "Codigos_DTC" in nombre_carpeta:
        return "DTC"
    elif "Mantenimiento" in nombre_carpeta or "Diagnostico" in nombre_carpeta:
        return "Procedimiento_Diagnostico"
    return "General"


# ==========================================
# 4. CHUNKING SEMÁNTICO (FRAGMENTACIÓN)
# ==========================================
def procesar_diccionario(texto_completo):
    """Separa el diccionario en términos individuales aislados"""
    chunks = []
    # Divide por los puntos de viñeta del diccionario
    terminos = re.split(r'\n•\s+', texto_completo)
    for i, term in enumerate(terminos):
        if term.strip() and len(term.strip()) > 10:
            chunks.append({
                "id": f"DIC_{i}", 
                "texto": f"Expresión coloquial/Término: {term.strip()}"
            })
    return chunks

def procesar_documento_tecnico(texto_completo, id_archivo):
    """Separa procedimientos (HTM240-PRC-XX) o códigos de fallo (HTM-XXXX) manteniendo su lógica"""
    chunks = []
    secciones = re.split(r'(HTM-\d{4}|HTM240-[A-Z]{3}-\d{3})', texto_completo)
    
    texto_acumulado = ""
    id_actual = id_archivo
    
    for parte in secciones:
        if re.match(r'(HTM-\d{4}|HTM240-[A-Z]{3}-\d{3})', parte):
            if texto_acumulado.strip():
                chunks.append({"id": id_actual, "texto": texto_acumulado.strip()})
            id_actual = parte
            texto_acumulado = parte + " "
        else:
            texto_acumulado += parte
            
    if texto_acumulado.strip():
        chunks.append({"id": id_actual, "texto": texto_acumulado.strip()})
        
    return chunks


# ==========================================
# 5. ORQUESTACIÓN PRINCIPAL
# ==========================================
def ejecutar_ingesta():
    conn = inicializar_bd()
    cursor = conn.cursor()
    
    print("\nIniciando escaneo de documentos...")
    for raiz, carpetas, archivos in os.walk(BASE_DIR):
        nombre_carpeta = os.path.basename(raiz)
        
        # REGLA ESTRICTA: Excluir documentos con información obsoleta
        if "00_Documentos_sustituidos" in nombre_carpeta:
            print(f"[*] Ignorando carpeta obsoleta: {nombre_carpeta}")
            continue
            
        categoria = determinar_categoria(nombre_carpeta)
        
        for archivo in archivos:
            ruta_completa = os.path.join(raiz, archivo)
            texto_extraido = ""
            
            # Leer nativamente PDFs o archivos de texto plano
            if archivo.lower().endswith(".pdf"):
                texto_extraido = extraer_texto_pdf(ruta_completa)
            elif archivo.lower().endswith(".txt") or archivo.lower().endswith(".md"):
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    texto_extraido = f.read()
            else:
                continue # Ignora imágenes u otros formatos no textuales
            
            if not texto_extraido.strip():
                continue
            
            # Seleccionar estrategia de segmentación
            if categoria == "Diccionario":
                chunks = procesar_diccionario(texto_extraido)
            else:
                chunks = procesar_documento_tecnico(texto_extraido, archivo)
            
            # Vectorizar e insertar
            fragmentos_insertados = 0
            for chunk in chunks:
                if len(chunk['texto']) < 20: # Ignorar frases demasiado cortas
                    continue
                
                # 1. Convertir texto a embedding matemático
                vector = embedder.encode(chunk['texto'])
                # 2. Convertir vector a binario puro para SQLite
                vector_bytes = vector.astype(np.float32).tobytes() 
                # 3. Asignar metadatos JSON
                versiones = determinar_versiones(chunk['texto'], chunk['id'])
                
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO documentos_rag 
                        (id_fragmento, texto, categoria, versiones_aplicables, embedding)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (chunk['id'], chunk['texto'], categoria, versiones, vector_bytes))
                    fragmentos_insertados += 1
                except Exception as e:
                    print(f"[!] Error insertando {chunk['id']}: {e}")
                    
            if fragmentos_insertados > 0:
                print(f"[+] Procesado: {archivo} ({categoria}) -> {fragmentos_insertados} fragmentos indexados.")

    conn.commit()
    conn.close()
    print("\n¡Ingesta completada con éxito! La base de datos vectorial está lista para consultas.")

if __name__ == "__main__":
    ejecutar_ingesta()