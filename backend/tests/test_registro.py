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
        "evidence_sufficiency": {
            "status": "partial",
            "requested_items": [
                {"item": "Dato documentado", "status": "supported"},
                {"item": "Dato ausente", "status": "not_found"},
            ],
            "missing_information": ["Dato ausente"],
        },
    }

    registro.registrar_consulta(
        peticion, respuesta, 1.23456,
        user_id=17, conversation_id="conv-1", message_id="msg-1",
    )

    linea = json.loads(destino.read_text(encoding="utf-8").splitlines()[0])
    assert linea["estado"] == "completada"
    assert linea["schema_version"] == 1
    assert linea["attempt_id"]
    assert linea["pregunta"] == "¿Qué significa HTM-0142?"
    assert linea["user_id"] == 17
    assert linea["conversation_id"] == "conv-1"
    assert linea["message_id"] == "msg-1"
    assert linea["documentos"] == ["HTM240-DTC-001.pdf", "HTM240-MAN-001.pdf"]
    assert linea["evidencia"] == "high"
    assert linea["suficiencia_evidencia"] == {
        "estado": "partial",
        "elementos_solicitados": 2,
        "informacion_no_localizada": 1,
    }
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
    assert linea["attempt_id"]
    assert linea["error"] == "RuntimeError"
    assert "traceback" not in linea


def test_cada_reintento_tiene_un_attempt_id_distinto(monkeypatch, tmp_path):
    destino = tmp_path / "logs" / "consultas.jsonl"
    monkeypatch.setattr(registro, "RUTA_REGISTRO", destino)
    peticion = SimpleNamespace(
        message="¿Qué significa HTM-0101?",
        engine_version="V1.1",
        profile=SimpleNamespace(value="user"),
    )

    registro.registrar_consulta(peticion, {}, 0.2, estado="error", error="RuntimeError", message_id="msg-1")
    registro.registrar_consulta(peticion, {}, 0.3, estado="error", error="RuntimeError", message_id="msg-1")

    lineas = [json.loads(linea) for linea in destino.read_text(encoding="utf-8").splitlines()]
    assert len(lineas) == 2
    assert lineas[0]["message_id"] == lineas[1]["message_id"] == "msg-1"
    assert lineas[0]["attempt_id"] != lineas[1]["attempt_id"]


def test_registra_codigos_de_alertas_seguridad_sin_duplicados(monkeypatch, tmp_path):
    destino = tmp_path / "consultas.jsonl"
    monkeypatch.setattr(registro, "RUTA_REGISTRO", destino)
    peticion = SimpleNamespace(
        message="Se ha encendido el testigo TES-05",
        engine_version="V2.0",
        profile=SimpleNamespace(value="user"),
    )
    respuesta = {
        "safety_alerts": [
            {"code": "high_voltage", "severity": "critical", "title": "Aviso", "message": "Texto"},
            {"code": "high_voltage", "severity": "critical", "title": "Aviso", "message": "Texto"},
        ]
    }

    registro.registrar_consulta(peticion, respuesta, 0.4, message_id="msg-5")

    linea = json.loads(destino.read_text(encoding="utf-8").splitlines()[0])
    assert linea["alertas_seguridad"] == ["high_voltage"]


def test_registra_resumen_de_revision_de_afirmaciones_sin_guardar_detalles(monkeypatch, tmp_path):
    destino = tmp_path / "consultas.jsonl"
    monkeypatch.setattr(registro, "RUTA_REGISTRO", destino)
    peticion = SimpleNamespace(
        message="¿Qué significa HTM-0101?",
        engine_version="V2.0",
        profile=SimpleNamespace(value="user"),
    )
    respuesta = {
        "claim_verification": {
            "status": "needs_review",
            "claims_total": 3,
            "claims_supported": 2,
            "claims": [{"claim": "dato privado que no debe copiarse al log"}],
        }
    }

    registro.registrar_consulta(peticion, respuesta, 0.5, message_id="msg-r04")

    linea = json.loads(destino.read_text(encoding="utf-8").splitlines()[0])
    assert linea["revision_afirmaciones"] == {
        "estado": "needs_review",
        "total": 3,
        "con_respaldo": 2,
    }
    assert "dato privado que no debe copiarse al log" not in destino.read_text(encoding="utf-8")
