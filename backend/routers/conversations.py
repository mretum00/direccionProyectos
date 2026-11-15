"""Conversaciones guardadas (solo se usan si VITE_REMOTE_CONVERSATIONS=true en el frontend)."""

from fastapi import APIRouter, HTTPException, status

from db.repositories import ConversationRepository
from models.schemas import Conversation, ConversationsListResponse

router = APIRouter(prefix="/api", tags=["conversations"])
repository = ConversationRepository()


@router.get("/conversations", response_model=ConversationsListResponse)
def list_conversations():
    """Listar las conversaciones guardadas (la más reciente primero)."""
    return {"conversations": repository.list_all()}


@router.put("/conversations", status_code=status.HTTP_204_NO_CONTENT)
def save_conversation(conversation: Conversation):
    """Guardar una conversación: la crea si no existe y la reemplaza si ya existe."""
    repository.save(conversation.model_dump(mode="json"))


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str):
    """Borrar una conversación (404 si no existe)."""
    if not repository.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
