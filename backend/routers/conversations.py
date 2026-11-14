"""Conversaciones guardadas (solo se usan si VITE_REMOTE_CONVERSATIONS=true en el frontend)."""

from fastapi import APIRouter, HTTPException

from db import conversations_store as store
from models.schemas import Conversation, ConversationsListResponse

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations", response_model=ConversationsListResponse)
def list_conversations():
    """Listar las conversaciones guardadas (la más reciente primero)."""
    return {"conversations": store.list_conversations()}


@router.put("/conversations", response_model=Conversation)
def save_conversation(conversation: Conversation):
    """Guardar una conversación: la crea si no existe y la reemplaza si ya existe."""
    store.save_conversation(conversation.model_dump(mode="json"))
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Borrar una conversación (404 si no existe)."""
    if not store.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"message": "Conversación eliminada"}
