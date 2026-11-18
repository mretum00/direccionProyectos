"""Fechas en el formato que guarda la BD de la aplicación (ISO 8601 en UTC, igual que `Date.toISOString()`)."""

from datetime import datetime, timedelta, timezone


def a_iso(fecha: datetime) -> str:
    return fecha.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ahora_iso(mas_horas: int = 0) -> str:
    return a_iso(datetime.now(timezone.utc) + timedelta(hours=mas_horas))
