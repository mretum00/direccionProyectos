from fastapi import APIRouter, HTTPException

from models.schemas import Conversation

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations")
async def list_conversations():
    """Listar conversaciones guardadas."""
    # TODO: listar desde persistencia
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/conversations")
async def create_conversation(conversation: Conversation):
    """Crear una conversación."""
    # TODO: guardar conversación
    _ = conversation
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Recuperar una conversación por id."""
    # TODO: leer conversación
    _ = conv_id
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/conversations")
async def update_conversation(conversation: Conversation):
    """Actualizar una conversación completa."""
    # TODO: actualizar conversación
    _ = conversation
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Eliminar una conversación."""
    # TODO: borrar conversación
    _ = conv_id
    raise HTTPException(status_code=501, detail="Not implemented yet")
