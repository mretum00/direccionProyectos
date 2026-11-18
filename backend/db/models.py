"""
Modelos Peewee de las tablas SQLite del backend.

Hay DOS bases de datos, separadas a propósito:

- `rag_db` -> thermodrive_rag.db (settings.db_path): fragmentos de los manuales (`rag_documents`).
  La genera backend/db/database_generator.py, que la BORRA y la vuelve a crear cada vez.
- `app_db` -> thermodrive_app.db (settings.app_db_path): usuarios (con su sesión) y el historial
  de conversaciones. Se crea sola al arrancar el backend (`init_app_db`) y nunca se borra.

Los modelos solo describen las tablas. Quien lee y escribe en ellas son los repositorios
(backend/db/repositories/): nadie más debería usar estos modelos directamente.
"""

from peewee import (
    AutoField,
    BlobField,
    BooleanField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

from playhouse.migrate import SqliteMigrator, migrate

from config import settings

# Peewee no abre el archivo hasta la primera consulta: los repositorios abren y cierran la conexión en cada operación.
rag_db = SqliteDatabase(str(settings.db_path))

# foreign_keys=1: SQLite no aplica las claves ajenas (ni el borrado en cascada) si no se activa.
app_db = SqliteDatabase(str(settings.app_db_path), pragmas={"foreign_keys": 1, "journal_mode": "wal"})


# --- BD del RAG ---------------------------------------------------------------


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


# --- BD de la aplicación --------------------------------------------------------
# Las fechas se guardan como texto ISO 8601 en UTC ("2026-11-18T10:00:00.000Z"), el mismo
# formato que usa el frontend: así se pueden ordenar y comparar como cadenas.


class AppModel(Model):
    class Meta:
        database = app_db


class User(AppModel):
    """Usuario y su sesión. Cada usuario tiene como mucho UNA sesión: iniciar sesión en otro
    navegador sustituye el token y cierra la anterior."""

    id = AutoField()
    username = TextField(unique=True)             # se guarda en minúsculas: el login no distingue mayúsculas
    password_hash = TextField()                   # pbkdf2_sha256$iteraciones$sal$hash (nunca la contraseña)
    created_at = TextField()
    # Sesión actual. Solo se guarda el hash del token: si se filtra la BD, el token no sirve.
    # Los dos a None = sin sesión iniciada.
    token_hash = TextField(null=True, unique=True)
    token_expires = TextField(null=True)

    class Meta:
        table_name = "users"


class Conversation(AppModel):
    id = TextField(primary_key=True)              # UUID generado por el frontend al empezar el chat
    user = ForeignKeyField(User, backref="conversations", on_delete="CASCADE")
    title = TextField()
    favorite = BooleanField(default=False)
    engine_version = TextField(default="")
    profile = TextField(default="")               # mechanic | user
    created_at = TextField()
    updated_at = TextField(index=True)

    class Meta:
        table_name = "conversations"


class Message(AppModel):
    seq = AutoField()                             # orden de los mensajes dentro de la conversación
    id = TextField(unique=True)                   # UUID público del mensaje
    conversation = ForeignKeyField(Conversation, backref="messages", on_delete="CASCADE")
    role = TextField()                            # user | assistant
    content = TextField()
    # Versión y perfil con los que se hizo la pregunta: se pueden cambiar a mitad de un chat,
    # así que cada mensaje guarda los suyos (la conversación solo guarda los últimos usados).
    engine_version = TextField(default="")
    profile = TextField(default="")
    response = TextField(null=True)               # JSON con evidencia y fuentes (solo mensajes del asistente)
    created_at = TextField()

    class Meta:
        table_name = "messages"


APP_TABLES = [User, Conversation, Message]


def init_app_db() -> None:
    """Crea las tablas de la aplicación si no existen (no toca las que ya hay)."""
    settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
    with app_db.connection_context():
        # Antes de create_tables: este crea el índice único de users.token_hash y, si la columna aún
        # no existe, SQLite tomaría "token_hash" como un texto fijo (índice inútil o error de UNIQUE).
        if User._meta.table_name in app_db.get_tables():
            _move_sessions_to_users()
        app_db.create_tables(APP_TABLES, safe=True)
        _add_message_selection_columns()


def _add_message_selection_columns() -> None:
    """BD creadas antes de guardar la versión por mensaje: añade las columnas y las rellena
    con la última versión y perfil de su conversación (lo único que se sabía de ellas)."""
    existing = {column.name for column in app_db.get_columns(Message._meta.table_name)}
    missing = [name for name in ("engine_version", "profile") if name not in existing]
    if not missing:
        return

    migrator = SqliteMigrator(app_db)
    with app_db.atomic():
        migrate(*(migrator.add_column(Message._meta.table_name, name, getattr(Message, name)) for name in missing))
        for name in missing:
            app_db.execute_sql(
                f"UPDATE messages SET {name} = "
                f"(SELECT {name} FROM conversations WHERE conversations.id = messages.conversation_id)"
            )


def _move_sessions_to_users() -> None:
    """BD creadas cuando las sesiones tenían su propia tabla (`sessions`): añade las columnas del
    token a `users` y borra la tabla vieja. Las sesiones abiertas se pierden: hay que volver a entrar."""
    existing = {column.name for column in app_db.get_columns(User._meta.table_name)}
    missing = [name for name in ("token_hash", "token_expires") if name not in existing]
    with app_db.atomic():
        if missing:
            migrator = SqliteMigrator(app_db)
            # Columnas sin índice: el índice único de token_hash lo crea create_tables justo después
            # (así hay uno solo, con el mismo nombre que en una BD nueva).
            migrate(*(migrator.add_column(User._meta.table_name, name, TextField(null=True)) for name in missing))
        app_db.execute_sql("DROP TABLE IF EXISTS sessions")
