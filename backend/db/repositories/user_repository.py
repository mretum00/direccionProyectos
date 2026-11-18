"""Repositorio de la tabla `users` (usuarios y su sesión: hash del token y caducidad)."""

from peewee import IntegrityError

from db.fechas import ahora_iso
from db.models import User, app_db


class UsernameTakenError(Exception):
    """Ya existe un usuario con ese nombre."""


class UserRepository:
    def create(self, username: str, password_hash: str) -> User:
        """Crea el usuario. Lanza UsernameTakenError si el nombre ya está cogido."""
        try:
            with app_db.connection_context():
                return User.create(username=username, password_hash=password_hash, created_at=ahora_iso())
        except IntegrityError as exc:
            raise UsernameTakenError(username) from exc

    def get_by_username(self, username: str) -> User | None:
        with app_db.connection_context():
            return User.get_or_none(User.username == username)

    def set_token(self, user: User, token_hash: str, ttl_hours: int) -> None:
        """Guarda la sesión nueva del usuario. Sustituye a la anterior, que deja de valer."""
        with app_db.connection_context():
            User.update(token_hash=token_hash, token_expires=ahora_iso(mas_horas=ttl_hours)).where(
                User.id == user.id
            ).execute()

    def get_by_token(self, token_hash: str) -> User | None:
        """Usuario cuyo token es este y no ha caducado (None si no existe o ya caducó)."""
        with app_db.connection_context():
            return User.get_or_none((User.token_hash == token_hash) & (User.token_expires > ahora_iso()))

    def clear_token(self, token_hash: str) -> None:
        """Cierra la sesión de ese token (si existe)."""
        with app_db.connection_context():
            User.update(token_hash=None, token_expires=None).where(User.token_hash == token_hash).execute()
