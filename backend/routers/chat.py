"""
POST /api/chat: recibe la pregunta del usuario, devuelve la respuesta del asistente y
guarda las dos en el historial del usuario.

1. Si esa pregunta (`message_id`) ya estaba guardada con su respuesta, devuelve lo guardado:
   reintentar tras cancelar o perder la conexión no la duplica ni vuelve a llamar al RAG.
2. Lee de la BD los últimos mensajes de la conversación (contexto para el RAG).
3. Ejecuta el pipeline RAG (services/rag_pipeline.py, sin cambios).
4. Guarda pregunta + respuesta juntas. Si el RAG falla no se guarda nada, así el
   frontend puede reintentar la misma pregunta sin duplicarla.

POST /api/chat/{message_id}/cancel: el usuario canceló la pregunta. Si ya estaba guardada se
borra; si aún se está respondiendo, se marca para que no se guarde al terminar.
"""

import logging
import threading
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from peewee import IntegrityError

from config import settings
from db.fechas import ahora_iso
from db.models import User
from db.repositories import ConversationRepository, NewMessage
from models.schemas import ChatRequest, ChatResponse
from services import rag_pipeline
from services.auth import usuario_actual

logger = logging.getLogger("ThermoDriveRAG")

router = APIRouter(prefix="/api", tags=["chat"])

conversaciones = ConversationRepository()

# Preguntas canceladas mientras se respondían, como (id del usuario, id de la pregunta): al terminar
# el RAG no se guardan.
# El candado hace que "comprobar si está cancelada + guardar" y "cancelar" no se mezclen.
_canceladas: set[tuple[int, str]] = set()
_candado = threading.Lock()


def _cancelada(user: User, question_id: str) -> HTTPException | None:
    """Si la pregunta se canceló, la quita de la lista y devuelve el error a responder."""
    clave = (user.id, question_id)
    if clave not in _canceladas:
        return None
    _canceladas.discard(clave)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La consulta se ha cancelado")


def _respuesta_guardada(user: User, conversation_id: str, question_id: str) -> dict | None:
    """La respuesta ya guardada a esa pregunta, con el formato de ChatResponse (None si no la hay)."""
    encontrado = conversaciones.find_exchange(user, conversation_id, question_id)
    if encontrado is None:
        return None
    conversation, answer = encontrado
    return {
        **(answer["response"] or {}),
        "message": {"id": answer["id"], "content": answer["content"]},
        "conversation": conversation,
    }


# `def` (no `async def`) a propósito: FastAPI lo ejecuta en un hilo aparte y las
# llamadas lentas (embeddings, SQLite, Groq) no bloquean al resto de peticiones.
@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
def chat(request: ChatRequest, user: User = Depends(usuario_actual)):
    conversation_id = str(request.conversation_id)
    question_id = str(request.message_id)
    if conversaciones.exists_for_other_user(user, conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")

    guardada = _respuesta_guardada(user, conversation_id, question_id)
    if guardada is not None:
        return guardada
    if conversaciones.message_id_taken(question_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese id de mensaje ya está en uso")
    with _candado:
        # La cancelación llegó antes que la pregunta: no se gasta una llamada al RAG.
        if (error := _cancelada(user, question_id)) is not None:
            raise error

    # Cada mensaje guarda la versión y el perfil con los que se preguntó: pueden cambiar dentro del chat.
    seleccion = {"engine_version": request.engine_version, "profile": request.profile.value}
    pregunta = NewMessage(id=question_id, role="user", content=request.message, created_at=ahora_iso(), **seleccion)
    historial = conversaciones.recent_history(user, conversation_id, settings.chat_history_limit)

    try:
        respuesta = rag_pipeline.armar_respuesta(
            request.message,
            request.engine_version,
            request.profile.value,
            historial,
        )
    except Exception as exc:
        logger.exception("Error en el pipeline RAG")
        raise HTTPException(status_code=500, detail="Error interno al procesar la consulta") from exc

    mensaje = respuesta["message"]
    meta = {k: v for k, v in respuesta.items() if k != "message" and v is not None}
    contestacion = NewMessage(
        id=mensaje["id"],
        role="assistant",
        content=mensaje["content"],
        created_at=ahora_iso(),
        response=meta,
        **seleccion,
    )

    try:
        with _candado:
            if (error := _cancelada(user, question_id)) is not None:
                raise error
            conversation = conversaciones.add_exchange(
                user, conversation_id, request.engine_version, request.profile.value, pregunta, contestacion
            )
    except IntegrityError:
        # Un reintento de la misma pregunta llegó mientras esta seguía en curso y ya la guardó.
        guardada = _respuesta_guardada(user, conversation_id, question_id)
        if guardada is None:
            raise
        return guardada
    return {**respuesta, "conversation": conversation}


@router.post("/chat/{message_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_chat(message_id: UUID, user: User = Depends(usuario_actual)):
    """Cancela la pregunta: no queda en el historial aunque el RAG la haya terminado de responder."""
    question_id = str(message_id)
    with _candado:
        if not conversaciones.delete_exchange(user, question_id):
            _canceladas.add((user.id, question_id))
