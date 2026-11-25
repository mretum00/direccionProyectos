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
    assert {mensaje["engine_version"] for mensaje in historial} == {"V1.0"}


def test_historial_conserva_aclaracion_tecnica_para_resolver_el_seguimiento(base_datos_temporal):
    repositorio = ConversationRepository()
    usuario = crear_usuario("usuario4")
    conversation_id = str(uuid4())

    repositorio.add_exchange(
        usuario,
        conversation_id,
        "V2.0",
        "mechanic",
        NewMessage(
            str(uuid4()), "user", "¿Cómo compruebo la bomba auxiliar?",
            "2026-01-01T10:00:00Z", "V2.0", "mechanic",
        ),
        NewMessage(
            str(uuid4()), "assistant",
            "¿Te refieres a la bomba auxiliar A (CMP-02) o B (CMP-03)?",
            "2026-01-01T10:00:01Z", "V2.0", "mechanic",
            {"needs_clarification": True, "clarification_kind": "technical"},
        ),
    )

    historial = repositorio.recent_history(usuario, conversation_id, 6)

    assert [mensaje["role"] for mensaje in historial] == ["user", "assistant"]
    assert historial[-1]["clarification_kind"] == "technical"
    assert "CMP-02" in historial[-1]["content"]


def test_historial_sigue_excluyendo_aclaraciones_de_version(base_datos_temporal):
    repositorio = ConversationRepository()
    usuario = crear_usuario("usuario5")
    conversation_id = str(uuid4())

    repositorio.add_exchange(
        usuario,
        conversation_id,
        "",
        "mechanic",
        NewMessage(
            str(uuid4()), "user", "¿Qué significa HTM-0142?",
            "2026-01-01T10:00:00Z", "", "mechanic",
        ),
        NewMessage(
            str(uuid4()), "assistant",
            "Selecciona V1.0, V1.1 o V2.0.",
            "2026-01-01T10:00:01Z", "", "mechanic",
            {"needs_clarification": True, "clarification_kind": "engine_version"},
        ),
    )

    historial = repositorio.recent_history(usuario, conversation_id, 6)

    assert historial == []

def test_historial_conserva_la_version_de_cada_mensaje_si_cambia_en_el_chat(base_datos_temporal):
    repositorio = ConversationRepository()
    usuario = crear_usuario("usuario6")
    conversation_id = str(uuid4())

    repositorio.add_exchange(
        usuario, conversation_id, "V1.0", "mechanic",
        NewMessage(str(uuid4()), "user", "¿Qué intervalo corresponde?", "2026-01-01T10:00:00Z", "V1.0", "mechanic"),
        NewMessage(str(uuid4()), "assistant", "Respuesta de V1.0", "2026-01-01T10:00:01Z", "V1.0", "mechanic"),
    )
    repositorio.add_exchange(
        usuario, conversation_id, "V2.0", "mechanic",
        NewMessage(str(uuid4()), "user", "¿Y para esta versión?", "2026-01-01T10:00:02Z", "V2.0", "mechanic"),
        NewMessage(str(uuid4()), "assistant", "Respuesta de V2.0", "2026-01-01T10:00:03Z", "V2.0", "mechanic"),
    )

    historial = repositorio.recent_history(usuario, conversation_id, 4)

    assert [mensaje["engine_version"] for mensaje in historial] == [
        "V1.0", "V1.0", "V2.0", "V2.0",
    ]
