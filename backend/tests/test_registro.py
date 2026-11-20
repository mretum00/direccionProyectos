import json
from types import SimpleNamespace

from services import registro


def test_registra_consulta_completada_con_metadatos_y_fuentes(monkeypatch, tmp_path):
    destino = tmp_path / "logs" / "consultas.jsonl"
    monkeypatch.setattr(registro, "RUTA_REGISTRO", destino)
    peticion = SimpleNamespace(
        message="¿Qué significa HTM-0142?",
        engine_version="V2.0",
        profile=SimpleNamespace(value="mechanic"),
    )
    respuesta = {
        "evidence_status": "high",
        "needs_clarification": False,
        "sources": [
            {"document": "HTM240-DTC-001.pdf"},
            {"document": "HTM240-DTC-001.pdf"},
            {"document": "HTM240-MAN-001.pdf"},
        ],
    }

    registro.registrar_consulta(
        peticion, respuesta, 1.23456,
        user_id=17, conversation_id="conv-1", message_id="msg-1",
    )

    linea = json.loads(destino.read_text(encoding="utf-8").splitlines()[0])
    assert linea["estado"] == "completada"
    assert linea["user_id"] == 17
    assert linea["conversation_id"] == "conv-1"
    assert linea["message_id"] == "msg-1"
    assert linea["documentos"] == ["HTM240-DTC-001.pdf", "HTM240-MAN-001.pdf"]
    assert linea["evidencia"] == "high"
    assert linea["segundos"] == 1.235
    assert linea["fecha"].endswith("Z")


def test_registra_fallos_sin_guardar_un_mensaje_de_error_detallado(monkeypatch, tmp_path):
    destino = tmp_path / "consultas.jsonl"
    monkeypatch.setattr(registro, "RUTA_REGISTRO", destino)
    peticion = SimpleNamespace(
        message="Consulta de prueba",
        engine_version="V1.0",
        profile=SimpleNamespace(value="user"),
    )

    registro.registrar_consulta(
        peticion, {}, 0.25, estado="error", error="RuntimeError",
    )

    linea = json.loads(destino.read_text(encoding="utf-8").splitlines()[0])
    assert linea["estado"] == "error"
    assert linea["error"] == "RuntimeError"
    assert "traceback" not in linea
