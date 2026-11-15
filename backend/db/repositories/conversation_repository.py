"""Repositorio de la tabla `conversations` (historial de chat, un registro por conversación)."""

import json
from contextlib import contextmanager
from typing import Iterator

from db.models import ConversationRow, conversations_db


class ConversationRepository:
    @contextmanager
    def _session(self) -> Iterator[None]:
        """Abre la conexión y crea la tabla si no existe (el archivo nace en el primer uso)."""
        with conversations_db.connection_context():
            conversations_db.create_tables([ConversationRow], safe=True)
            yield

    def list_all(self) -> list[dict]:
        """Todas las conversaciones, la más reciente primero."""
        with self._session():
            filas = ConversationRow.select(ConversationRow.data).order_by(ConversationRow.updated_at.desc())
            return [json.loads(fila.data) for fila in filas]

    def save(self, conversation: dict) -> None:
        """Guarda una conversación: la crea si no existe y la reemplaza si ya existe."""
        with self._session():
            ConversationRow.replace(
                id=conversation["id"],
                updated_at=conversation["updated_at"],
                data=json.dumps(conversation, ensure_ascii=False),
            ).execute()

    def delete(self, conversation_id: str) -> bool:
        """Borra una conversación. Devuelve False si no existía."""
        with self._session():
            return ConversationRow.delete().where(ConversationRow.id == conversation_id).execute() > 0
