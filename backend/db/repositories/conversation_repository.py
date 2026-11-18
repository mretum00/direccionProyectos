"""Repositorio de las tablas `conversations` y `messages` (historial de chats de cada usuario)."""

import json
import uuid
from dataclasses import dataclass

from peewee import prefetch

from db.fechas import ahora_iso
from db.models import Conversation, Message, User, app_db


@dataclass
class NewMessage:
    id: str
    role: str
    content: str
    created_at: str
    engine_version: str = ""
    profile: str = ""
    response: dict | None = None


def _to_dict(conversation: Conversation, messages: list[Message]) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "favorite": conversation.favorite,
        "engine_version": conversation.engine_version,
        "profile": conversation.profile,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
                "engine_version": m.engine_version,
                "profile": m.profile,
                "response": json.loads(m.response) if m.response else None,
            }
            for m in sorted(messages, key=lambda m: m.seq)
        ],
    }


class ConversationRepository:
    """Todas las operaciones reciben el usuario: nadie puede leer ni tocar chats de otro."""

    def _get(self, user: User, conversation_id: str) -> Conversation | None:
        return Conversation.get_or_none((Conversation.id == conversation_id) & (Conversation.user == user))

    def _load(self, conversation: Conversation) -> dict:
        messages = list(conversation.messages.order_by(Message.seq))
        return _to_dict(conversation, messages)

    def list_for_user(self, user: User) -> list[dict]:
        """Conversaciones del usuario con sus mensajes, las más recientes primero (2 consultas en total)."""
        with app_db.connection_context():
            query = Conversation.select().where(Conversation.user == user).order_by(Conversation.updated_at.desc())
            return [_to_dict(c, list(c.messages)) for c in prefetch(query, Message.select())]

    def get(self, user: User, conversation_id: str) -> dict | None:
        with app_db.connection_context():
            conversation = self._get(user, conversation_id)
            return self._load(conversation) if conversation else None

    def exists_for_other_user(self, user: User, conversation_id: str) -> bool:
        with app_db.connection_context():
            return (
                Conversation.select()
                .where((Conversation.id == conversation_id) & (Conversation.user != user))
                .exists()
            )

    def message_id_taken(self, message_id: str) -> bool:
        """True si ya hay un mensaje con ese id (en cualquier conversación)."""
        with app_db.connection_context():
            return Message.select().where(Message.id == message_id).exists()

    def find_exchange(self, user: User, conversation_id: str, question_id: str) -> tuple[dict, dict] | None:
        """Si la pregunta `question_id` ya está guardada con su respuesta, devuelve (conversación, respuesta).

        Sirve para que reenviar la misma pregunta (reintento tras cancelar o perder la conexión)
        no la duplique: pregunta y respuesta se guardan juntas y seguidas en `add_exchange`.
        """
        with app_db.connection_context():
            conversation = self._get(user, conversation_id)
            if conversation is None:
                return None
            loaded = self._load(conversation)
        messages = loaded["messages"]
        for i, m in enumerate(messages[:-1]):
            if m["id"] == question_id and m["role"] == "user" and messages[i + 1]["role"] == "assistant":
                return loaded, messages[i + 1]
        return None

    def delete_exchange(self, user: User, question_id: str) -> bool:
        """Borra la pregunta `question_id` del usuario y la respuesta que la sigue (al cancelarla).

        Si la conversación se queda sin mensajes, se borra también. False si la pregunta no estaba guardada.
        """
        with app_db.connection_context(), app_db.atomic():
            question = (
                Message.select(Message, Conversation)
                .join(Conversation)
                .where((Message.id == question_id) & (Message.role == "user") & (Conversation.user == user))
                .get_or_none()
            )
            if question is None:
                return False
            conversation = question.conversation
            answer = (
                conversation.messages.where(Message.seq > question.seq).order_by(Message.seq).first()
            )
            ids = [question.seq] + ([answer.seq] if answer is not None and answer.role == "assistant" else [])
            Message.delete().where(Message.seq.in_(ids)).execute()
            last = conversation.messages.order_by(Message.seq.desc()).first()
            if last is None:
                conversation.delete_instance()
            else:
                # La conversación vuelve a quedar como estaba antes de la pregunta cancelada.
                conversation.updated_at = last.created_at
                conversation.engine_version = last.engine_version
                conversation.profile = last.profile
                conversation.save()
            return True

    def recent_history(self, user: User, conversation_id: str, limit: int) -> list[dict]:
        """Últimos `limit` mensajes (role, content) en orden cronológico, sin los avisos de aclaración."""
        with app_db.connection_context():
            conversation = self._get(user, conversation_id)
            if conversation is None:
                return []
            rows = conversation.messages.order_by(Message.seq.desc())
            history = []
            for m in rows:
                meta = json.loads(m.response) if m.response else {}
                # Los avisos de "elige la versión" no le aportan nada al modelo.
                if meta.get("needs_clarification"):
                    continue
                history.append({"role": m.role, "content": m.content})
                if len(history) == limit:
                    break
            return list(reversed(history))

    def add_exchange(
        self,
        user: User,
        conversation_id: str,
        engine_version: str,
        profile: str,
        question: NewMessage,
        answer: NewMessage,
    ) -> dict:
        """Guarda pregunta y respuesta juntas (o ninguna). Crea la conversación si es la primera pregunta."""
        with app_db.connection_context(), app_db.atomic():
            conversation = self._get(user, conversation_id)
            if conversation is None:
                conversation = Conversation.create(
                    id=conversation_id,
                    user=user,
                    title=question.content[:50],
                    created_at=question.created_at,
                    updated_at=answer.created_at,
                    engine_version=engine_version,
                    profile=profile,
                )
            else:
                conversation.updated_at = answer.created_at
                conversation.engine_version = engine_version
                conversation.profile = profile
                conversation.save()

            for m in (question, answer):
                Message.create(
                    id=m.id,
                    conversation=conversation,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at,
                    engine_version=m.engine_version,
                    profile=m.profile,
                    response=json.dumps(m.response, ensure_ascii=False) if m.response is not None else None,
                )
            return self._load(conversation)

    def update(self, user: User, conversation_id: str, title: str | None, favorite: bool | None) -> dict | None:
        with app_db.connection_context():
            conversation = self._get(user, conversation_id)
            if conversation is None:
                return None
            if title is not None:
                conversation.title = title
            if favorite is not None:
                conversation.favorite = favorite
            conversation.updated_at = ahora_iso()
            conversation.save()
            return self._load(conversation)

    def duplicate(self, user: User, conversation_id: str) -> dict | None:
        """Copia la conversación con todos sus mensajes (con ids nuevos)."""
        with app_db.connection_context(), app_db.atomic():
            original = self._get(user, conversation_id)
            if original is None:
                return None
            now = ahora_iso()
            copy = Conversation.create(
                id=str(uuid.uuid4()),
                user=user,
                title=f"{original.title} (copia)",
                favorite=False,
                engine_version=original.engine_version,
                profile=original.profile,
                created_at=now,
                updated_at=now,
            )
            for m in original.messages.order_by(Message.seq):
                Message.create(
                    id=str(uuid.uuid4()),
                    conversation=copy,
                    role=m.role,
                    content=m.content,
                    response=m.response,
                    created_at=m.created_at,
                    engine_version=m.engine_version,
                    profile=m.profile,
                )
            return self._load(copy)

    def delete(self, user: User, conversation_id: str) -> bool:
        """Borra la conversación y, en cascada, sus mensajes. False si no existía."""
        with app_db.connection_context():
            deleted = (
                Conversation.delete()
                .where((Conversation.id == conversation_id) & (Conversation.user == user))
                .execute()
            )
            return deleted > 0
