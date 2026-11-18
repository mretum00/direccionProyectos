"""Fechas en el formato que guarda la BD de la aplicación (ISO 8601 en UTC, igual que `Date.toISOString()`)."""

from datetime import datetime, timezone


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
