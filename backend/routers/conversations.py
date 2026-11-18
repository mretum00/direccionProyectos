"""
Historial de conversaciones del usuario que ha iniciado sesión.

Las conversaciones se crean solas con la primera pregunta (POST /api/chat); aquí se
listan, renombran, marcan como favoritas, duplican y borran.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from db.models import User
from db.repositories import ConversationRepository
from models.schemas import ConversationOut, ConversationsListResponse, ConversationUpdate
from services.auth import usuario_actual

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

repositorio = ConversationRepository()


def _no_encontrada() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")


@router.get("", response_model=ConversationsListResponse)
def list_conversations(user: User = Depends(usuario_actual)):
    return {"conversations": repositorio.list_for_user(user)}


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, user: User = Depends(usuario_actual)):
    conversation = repositorio.get(user, conversation_id)
    if conversation is None:
        raise _no_encontrada()
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(conversation_id: str, body: ConversationUpdate, user: User = Depends(usuario_actual)):
    conversation = repositorio.update(user, conversation_id, body.title, body.favorite)
    if conversation is None:
        raise _no_encontrada()
    return conversation


@router.post("/{conversation_id}/duplicate", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def duplicate_conversation(conversation_id: str, user: User = Depends(usuario_actual)):
    conversation = repositorio.duplicate(user, conversation_id)
    if conversation is None:
        raise _no_encontrada()
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, user: User = Depends(usuario_actual)):
    if not repositorio.delete(user, conversation_id):
        raise _no_encontrada()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
