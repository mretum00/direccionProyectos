import logging

from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse
from services import rag_pipeline

logger = logging.getLogger("ThermoDriveRAG")

router = APIRouter(prefix="/api", tags=["chat"])


# Endpoint síncrono a propósito: FastAPI lo ejecuta en un hilo del pool y las
# llamadas bloqueantes (embeddings, SQLite, Groq) no congelan el event loop.
@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
def chat(request: ChatRequest):
    try:
        result = rag_pipeline.armar_respuesta(
            request.message,
            request.engine_version,
            request.profile.value,
        )
    except Exception as exc:
        logger.exception("Error en el pipeline RAG")
        raise HTTPException(status_code=500, detail="Error interno al procesar la consulta") from exc

    if result is None:
        # Las funciones de rag_pipeline.py aún están vacías (devuelven None).
        raise HTTPException(
            status_code=501,
            detail="Pipeline RAG pendiente de implementar (backend/services/rag_pipeline.py)",
        )
    return result
