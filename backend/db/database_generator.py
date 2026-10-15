import os
import sqlite3
import json
import re
import numpy as np
import fitz
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

# Cargar el archivo .env desde la raíz del proyecto
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Leer variables del .env con valores por defecto (fallback)
DB_NAME = os.getenv("DB_NAME", "thermodrive_rag.db")
DB_PATH = os.path.join(PROJECT_ROOT, DB_NAME)

MANUALS_DIR = os.getenv("MANUALS_DIR", "manual_htm240")
BASE_DIR = os.path.join(PROJECT_ROOT, MANUALS_DIR)

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

print("Loading embedding model (this may take a few seconds the first time)...")
embedder = SentenceTransformer(MODEL_NAME)

# ==========================================
# 2. FUNCIONES DE BASE DE DATOS Y LECTURA
# ==========================================
def initialize_db():
    """Crea la base de datos SQLite y la tabla de vectores/metadatos"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rag_documents (
            chunk_id TEXT PRIMARY KEY,
            text TEXT,
            category TEXT,
            applicable_versions TEXT, -- Guardado como JSON string
            embedding BLOB -- Vector matemático guardado como datos binarios
        )
    ''')
    conn.commit()
    return conn

def extract_pdf_text(pdf_path):
    """Extrae el texto de un PDF página por página usando PyMuPDF"""
    text = ""
    try:
        document = fitz.open(pdf_path)
        for page in document:
            # Corrección del error de tipado forzando la conversión a string
            text += str(page.get_text("text")) + "\n"
        document.close()
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
    return text


# ==========================================
# 3. EXTRACCIÓN DE METADATOS
# ==========================================
def determine_versions(text, document_id):
    """Asigna las etiquetas de versión correspondientes para el filtrado posterior"""
    versions = ["V1.0", "V1.1", "V2.0"]
    
    if "HTM240-BOL-001" in document_id:
        versions = ["V1.0"]
    elif "HTM240-BOL-002" in document_id:
        versions = ["V1.1", "V2.0"]
    elif "ST-B200" in text or "PTC de 5 kW" in text:
        versions = ["V2.0"]
        
    return json.dumps(versions)

def determine_category(folder_name):
    """Clasifica el fragmento según su carpeta de origen"""
    if "Diccionario" in folder_name:
        return "Dictionary"
    elif "Codigos_DTC" in folder_name:
        return "DTC"
    elif "Mantenimiento" in folder_name or "Diagnostico" in folder_name:
        return "Diagnostic_Procedure"
    return "General"


# ==========================================
# 4. CHUNKING SEMÁNTICO (FRAGMENTACIÓN)
# ==========================================
def process_dictionary(full_text):
    """Separa el diccionario en términos individuales aislados"""
    chunks = []
    # Divide por los puntos de viñeta del diccionario
    terms = re.split(r'\n•\s+', full_text)
    for i, term in enumerate(terms):
        if term.strip() and len(term.strip()) > 10:
            chunks.append({
                "id": f"DIC_{i}", 
                "text": f"Colloquial expression/Term: {term.strip()}"
            })
    return chunks

def process_technical_document(full_text, file_id):
    """Separa procedimientos (HTM240-PRC-XX) o códigos de fallo (HTM-XXXX) manteniendo su lógica"""
    chunks = []
    sections = re.split(r'(HTM-\d{4}|HTM240-[A-Z]{3}-\d{3})', full_text)
    
    accumulated_text = ""
    current_id = file_id
    
    for part in sections:
        if re.match(r'(HTM-\d{4}|HTM240-[A-Z]{3}-\d{3})', part):
            if accumulated_text.strip():
                chunks.append({"id": current_id, "text": accumulated_text.strip()})
            current_id = part
            accumulated_text = part + " "
        else:
            accumulated_text += part
            
    if accumulated_text.strip():
        chunks.append({"id": current_id, "text": accumulated_text.strip()})
        
    return chunks


# ==========================================
# 5. ORQUESTACIÓN PRINCIPAL
# ==========================================
def run_ingestion():
    conn = initialize_db()
    cursor = conn.cursor()
    
    print("\nStarting document scan...")
    for root, folders, files in os.walk(BASE_DIR):
        folder_name = os.path.basename(root)
        
        # REGLA ESTRICTA: Excluir documentos con información obsoleta
        if "00_Documentos_sustituidos" in folder_name:
            print(f"[*] Ignoring obsolete folder: {folder_name}")
            continue
            
        category = determine_category(folder_name)
        
        for file in files:
            full_path = os.path.join(root, file)
            extracted_text = ""
            
            # Leer nativamente PDFs o archivos de texto plano
            if file.lower().endswith(".pdf"):
                extracted_text = extract_pdf_text(full_path)
            elif file.lower().endswith(".txt") or file.lower().endswith(".md"):
                with open(full_path, 'r', encoding='utf-8') as f:
                    extracted_text = f.read()
            else:
                continue # Ignora imágenes u otros formatos no textuales
            
            if not extracted_text.strip():
                continue
            
            # Seleccionar estrategia de segmentación
            if category == "Dictionary":
                chunks = process_dictionary(extracted_text)
            else:
                chunks = process_technical_document(extracted_text, file)
            
            # Vectorizar e insertar
            inserted_chunks = 0
            for chunk in chunks:
                if len(chunk['text']) < 20: # Ignorar frases demasiado cortas
                    continue
                
                # 1. Convertir texto a embedding matemático
                vector = embedder.encode(chunk['text'])
                # 2. Convertir vector a binario puro para SQLite
                vector_bytes = vector.astype(np.float32).tobytes() 
                # 3. Asignar metadatos JSON
                versions = determine_versions(chunk['text'], chunk['id'])
                
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO rag_documents 
                        (chunk_id, text, category, applicable_versions, embedding)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (chunk['id'], chunk['text'], category, versions, vector_bytes))
                    inserted_chunks += 1
                except Exception as e:
                    print(f"[!] Error inserting {chunk['id']}: {e}")
                    
            if inserted_chunks > 0:
                print(f"[+] Processed: {file} ({category}) -> {inserted_chunks} chunks indexed.")

    conn.commit()
    conn.close()
    print("\nIngestion completed successfully! The vector database is ready for queries.")

if __name__ == "__main__":
    run_ingestion()