from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Consulta RAG. La lógica se implementará más adelante."""
    # TODO: RAG + LLM (Groq)
    # 1. Buscar fragmentos en SQLite filtrando por engine/engine_version
    # 2. Construir contexto
    # 3. Generar respuesta estructurada con fuentes
    _ = request
    raise HTTPException(status_code=501, detail="Not implemented yet")
