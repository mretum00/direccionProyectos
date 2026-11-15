"""
Modelos Peewee de las tablas SQLite del backend.

Hay dos bases de datos, cada una en su archivo:
  - `rag_db`            -> thermodrive_rag.db (settings.db_path): tabla `rag_documents`
  - `conversations_db`  -> conversations.db (settings.conversations_db_path): tabla `conversations`

Los modelos solo describen las tablas. Quien lee y escribe en ellas son los repositorios
(backend/db/repositories/), uno por tabla: nadie más debería usar estos modelos directamente.
"""

from peewee import BlobField, IntegerField, Model, SqliteDatabase, TextField

from config import settings

# Peewee no abre el archivo hasta la primera consulta: los repositorios abren y cierran la conexión en cada operación.
rag_db = SqliteDatabase(str(settings.db_path))
conversations_db = SqliteDatabase(str(settings.conversations_db_path))


class RagChunk(Model):
    """Un fragmento de un documento técnico."""

    chunk_id = TextField(primary_key=True)
    text = TextField(null=True)
    category = TextField(null=True)               # Manual | DTC | Dictionary
    applicable_versions = TextField(null=True)    # lista JSON: '["V1.0", "V1.1"]'
    embedding = BlobField(null=True)              # float32 normalizado
    page = IntegerField(null=True)                # página del PDF donde empieza el fragmento
    section = TextField(null=True)                # apartado, código de entrada o de caso

    class Meta:
        database = rag_db
        table_name = "rag_documents"


class ConversationRow(Model):
    """Una conversación del historial de chat."""

    id = TextField(primary_key=True)
    updated_at = TextField()
    data = TextField()                            # la conversación entera, en JSON

    class Meta:
        database = conversations_db
        table_name = "conversations"
