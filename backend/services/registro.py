"""Registro de consultas procesadas en JSON Lines (backend/logs/consultas.jsonl).

El historial completo de mensajes vive en `thermodrive_app.db`. Este archivo es un
registro de auditoría ligero: permite revisar consultas, estado del RAG, evidencia,
fuentes y duración, incluidas las consultas que fallan antes de guardarse en el chat.
"""

import json
from datetime import datetime, timezone
from threading import Lock

from config import BACKEND_DIR

RUTA_REGISTRO = BACKEND_DIR / "logs" / "consultas.jsonl"
_CANDADO_REGISTRO = Lock()


def registrar_consulta(
    request,
    respuesta: dict | None,
    segundos: float,
    *,
    user_id: int | str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    estado: str = "completada",
    error: str | None = None,
) -> None:
    """Añade una consulta al registro sin guardar la respuesta completa ni credenciales.

    `estado` suele ser `completada` o `error`. En errores solo se guarda el tipo de
    excepción, no su mensaje, para evitar registrar accidentalmente información sensible.
    """
    respuesta = respuesta or {}
    perfil = getattr(request.profile, "value", request.profile)
    documentos = sorted({
        fuente.get("document")
        for fuente in (respuesta.get("sources") or [])
        if fuente.get("document")
    })

    linea = {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "pregunta": request.message,
        "version": request.engine_version,
        "perfil": perfil,
        "estado": estado,
        "evidencia": respuesta.get("evidence_status"),
        "aclaracion": bool(respuesta.get("needs_clarification", False)),
        "documentos": documentos,
        "segundos": round(max(0.0, float(segundos)), 3),
    }
    if error:
        linea["error"] = error

    RUTA_REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(linea, ensure_ascii=False, separators=(",", ":")) + "\n"
    # Un único bloqueo evita que dos peticiones del mismo proceso mezclen líneas.
    with _CANDADO_REGISTRO:
        with RUTA_REGISTRO.open("a", encoding="utf-8") as archivo:
            archivo.write(contenido)
