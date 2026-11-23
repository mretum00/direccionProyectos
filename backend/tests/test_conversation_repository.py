from uuid import uuid4

import pytest

from config import settings
from db.models import APP_TABLES, User, app_db
from db.repositories import ConversationRepository, NewMessage


@pytest.fixture
def base_datos_temporal(tmp_path):
    """Cada prueba usa su SQLite temporal, nunca la BD real del desarrollador."""
    app_db.close()
    app_db.init(str(tmp_path / "app_test.db"), pragmas={"foreign_keys": 1, "journal_mode": "wal"})
    with app_db.connection_context():
        app_db.create_tables(APP_TABLES, safe=True)
    yield
    app_db.close()
    app_db.init(str(settings.app_db_path), pragmas={"foreign_keys": 1, "journal_mode": "wal"})


def crear_usuario(nombre):
    with app_db.connection_context():
        return User.create(username=nombre, password_hash="hash-de-prueba", created_at="2026-01-01T10:00:00Z")


def test_persiste_intercambio_y_solo_lo_devuelve_a_su_propietario(base_datos_temporal):
    repositorio = ConversationRepository()
    usuario = crear_usuario("usuario1")
    otro_usuario = crear_usuario("usuario2")
    conversation_id = str(uuid4())
    question_id = str(uuid4())

    conversation = repositorio.add_exchange(
        usuario,
        conversation_id,
        "V2.0",
        "mechanic",
        NewMessage(question_id, "user", "¿Qué significa HTM-0142?", "2026-01-01T10:00:00Z", "V2.0", "mechanic"),
        NewMessage(str(uuid4()), "assistant", "Respuesta basada en el manual", "2026-01-01T10:00:02Z", "V2.0", "mechanic", {"evidence_status": "high"}),
    )

    recuperada = repositorio.get(usuario, conversation_id)

    assert conversation["id"] == conversation_id
    assert [mensaje["role"] for mensaje in recuperada["messages"]] == ["user", "assistant"]
    assert recuperada["messages"][1]["response"]["evidence_status"] == "high"
    assert repositorio.get(otro_usuario, conversation_id) is None
    assert repositorio.list_for_user(otro_usuario) == []


def test_historial_reciente_se_devuelve_en_orden_cronologico(base_datos_temporal):
    repositorio = ConversationRepository()
    usuario = crear_usuario("usuario3")
    conversation_id = str(uuid4())

    repositorio.add_exchange(
        usuario, conversation_id, "V1.0", "user",
        NewMessage(str(uuid4()), "user", "Primera pregunta", "2026-01-01T10:00:00Z", "V1.0", "user"),
        NewMessage(str(uuid4()), "assistant", "Primera respuesta", "2026-01-01T10:00:01Z", "V1.0", "user"),
    )
    repositorio.add_exchange(
        usuario, conversation_id, "V1.0", "user",
        NewMessage(str(uuid4()), "user", "Segunda pregunta", "2026-01-01T10:00:02Z", "V1.0", "user"),
        NewMessage(str(uuid4()), "assistant", "Segunda respuesta", "2026-01-01T10:00:03Z", "V1.0", "user"),
    )

    historial = repositorio.recent_history(usuario, conversation_id, 3)

    assert [mensaje["content"] for mensaje in historial] == [
        "Primera respuesta", "Segunda pregunta", "Segunda respuesta",
    ]
    # Cada mensaje lleva la versión con la que se hizo: puede cambiar dentro del chat.
    assert {mensaje["engine_version"] for mensaje in historial} == {"V1.0"}
