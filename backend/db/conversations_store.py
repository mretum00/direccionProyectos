"""Persistencia de conversaciones en SQLite (fichero independiente de la BD vectorial)."""

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    data       TEXT NOT NULL
)
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.conversations_db_path)
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def list_conversations() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT data FROM conversations ORDER BY updated_at DESC").fetchall()
    return [json.loads(data) for (data,) in rows]


def get_conversation(conv_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT data FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    return json.loads(row[0]) if row else None


def save_conversation(conversation: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO conversations (id, updated_at, data) VALUES (?, ?, ?)",
            (conversation["id"], conversation.get("updated_at", ""), json.dumps(conversation, ensure_ascii=False)),
        )


def delete_conversation(conv_id: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    return cursor.rowcount > 0
