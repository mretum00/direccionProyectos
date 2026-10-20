from fastapi import APIRouter, HTTPException

from db import conversations_store as store
from models.schemas import Conversation

router = APIRouter(prefix="/api", tags=["conversations"])


def _dump(conversation: Conversation) -> dict:
    return conversation.model_dump(mode="json")


@router.get("/conversations")
def list_conversations():
    """Listar conversaciones guardadas (más recientes primero)."""
    return {"conversations": store.list_conversations()}


@router.post("/conversations")
def create_conversation(conversation: Conversation):
    """Crear una conversación."""
    data = _dump(conversation)
    store.save_conversation(data)
    return {"message": "Conversación creada", "data": data}


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str):
    """Recuperar una conversación por id."""
    data = store.get_conversation(conv_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return data


@router.put("/conversations")
def update_conversation(conversation: Conversation):
    """Actualizar una conversación completa."""
    if store.get_conversation(conversation.id) is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    data = _dump(conversation)
    store.save_conversation(data)
    return {"message": "Conversación actualizada", "data": data}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Eliminar una conversación."""
    if not store.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"message": f"Conversación {conv_id} eliminada correctamente"}
