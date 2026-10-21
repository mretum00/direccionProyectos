"""
Configuración centralizada del backend.

Todos los valores salen de variables de entorno (archivo `.env` en la raíz del
repositorio). Ningún otro módulo debe leer `os.environ` ni hardcodear rutas,
modelos, puertos u orígenes: se importan desde aquí.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_VERSION = "1.0.0"

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Carga explícita del .env de la raíz, sin depender del directorio desde el que
# se lance uvicorn. Las variables ya definidas en el entorno tienen prioridad.
load_dotenv(PROJECT_ROOT / ".env")


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"La variable de entorno {name} debe ser un entero, recibido: {raw!r}") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"La variable de entorno {name} debe ser un número, recibido: {raw!r}") from exc


def _get_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in _get_str(name, default).split(",") if item.strip()]


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


@dataclass(frozen=True)
class Settings:
    # --- Servidor ---
    api_host: str
    api_port: int
    cors_origins: list[str]
    log_level: str

    # --- Rutas ---
    db_path: Path
    conversations_db_path: Path
    manuals_dir: Path

    # --- IA ---
    embedding_model: str
    groq_api_key: str | None
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_reasoning_effort: str

    # --- RAG ---
    rag_top_k: int
    rag_dictionary_top_k: int
    rag_dictionary_min_score: float
    rag_evidence_min_score: float
    rag_evidence_high_score: float
    rag_code_match_bonus: float
    rag_chunk_size: int
    rag_chunk_overlap: int
    source_excerpt_chars: int


def load_settings() -> Settings:
    return Settings(
        api_host=_get_str("API_HOST", "127.0.0.1"),
        api_port=_get_int("API_PORT", 8000),
        cors_origins=_get_list("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"),
        log_level=_get_str("LOG_LEVEL", "INFO").upper(),
        # DB_NAME es relativo a la raíz del repo (o ruta absoluta).
        db_path=_resolve(PROJECT_ROOT, _get_str("DB_NAME", "thermodrive_rag.db")),
        # Conversaciones en un fichero aparte: guardar una conversación no debe
        # invalidar la caché de embeddings de la BD vectorial.
        conversations_db_path=_resolve(PROJECT_ROOT, _get_str("CONVERSATIONS_DB_NAME", "conversations.db")),
        # MANUALS_DIR es relativo a backend/db/ (o ruta absoluta).
        manuals_dir=_resolve(BACKEND_DIR / "db", _get_str("MANUALS_DIR", "manual_htm240")),
        embedding_model=_get_str("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        llm_model=_get_str("LLM_MODEL", "openai/gpt-oss-20b"),
        llm_temperature=_get_float("LLM_TEMPERATURE", 0.1),
        # Tokens máximos de la respuesta (incluye el razonamiento interno de gpt-oss).
        llm_max_tokens=_get_int("LLM_MAX_TOKENS", 4096),
        # low | medium | high para modelos que razonan (gpt-oss). Vacío = no se envía.
        llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "low").strip(),
        rag_top_k=_get_int("RAG_TOP_K", 5),
        rag_dictionary_top_k=_get_int("RAG_DICTIONARY_TOP_K", 3),
        rag_dictionary_min_score=_get_float("RAG_DICTIONARY_MIN_SCORE", 0.3),
        # Similitud del mejor fragmento: por debajo de MIN no se responde; desde HIGH la evidencia es alta.
        rag_evidence_min_score=_get_float("RAG_EVIDENCE_MIN_SCORE", 0.3),
        rag_evidence_high_score=_get_float("RAG_EVIDENCE_HIGH_SCORE", 0.5),
        # Extra de puntuación para los fragmentos que contienen el código de avería exacto de la consulta.
        rag_code_match_bonus=_get_float("RAG_CODE_MATCH_BONUS", 0.15),
        rag_chunk_size=_get_int("RAG_CHUNK_SIZE", 800),
        rag_chunk_overlap=_get_int("RAG_CHUNK_OVERLAP", 200),
        source_excerpt_chars=_get_int("SOURCE_EXCERPT_CHARS", 200),
    )


settings = load_settings()
