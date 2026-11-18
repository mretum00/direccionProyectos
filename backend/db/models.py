"""
Modelo Peewee de la tabla SQLite del backend.

Hay una base de datos: `rag_db` -> thermodrive_rag.db (settings.db_path), tabla `rag_documents`.
Las conversaciones del chat no se guardan en el backend: viven en el localStorage del navegador.

El modelo solo describe la tabla. Quien lee y escribe en ella es el repositorio
(backend/db/repositories/): nadie más debería usar este modelo directamente.
"""

from peewee import BlobField, IntegerField, Model, SqliteDatabase, TextField

from config import settings

# Peewee no abre el archivo hasta la primera consulta: el repositorio abre y cierra la conexión en cada operación.
rag_db = SqliteDatabase(str(settings.db_path))


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
