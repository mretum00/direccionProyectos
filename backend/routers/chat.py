"""POST /api/chat: recibe la pregunta del usuario y devuelve la respuesta del asistente."""

import logging

from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse
from services import rag_pipeline

logger = logging.getLogger("ThermoDriveRAG")

router = APIRouter(prefix="/api", tags=["chat"])


# `def` (no `async def`) a propósito: FastAPI lo ejecuta en un hilo aparte y las
# llamadas lentas (embeddings, SQLite, Groq) no bloquean al resto de peticiones.
@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
def chat(request: ChatRequest):
    try:
        return rag_pipeline.armar_respuesta(
            request.message,
            request.engine_version,
            request.profile.value,
            [item.model_dump() for item in request.history],
        )
    except Exception as exc:
        logger.exception("Error en el pipeline RAG")
        raise HTTPException(status_code=500, detail="Error interno al procesar la consulta") from exc
