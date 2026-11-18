"""
Registro, inicio de sesión y sesiones de usuario.

- Las contraseñas se guardan con PBKDF2-SHA256 + sal aleatoria (librería estándar, sin dependencias).
- Al iniciar sesión se genera un token aleatorio que el frontend envía en cada petición
  (cabecera `Authorization: Bearer <token>`). En la BD solo se guarda su hash SHA-256, en la
  propia fila del usuario: cada usuario tiene una sola sesión, y entrar desde otro navegador
  cierra la anterior.
- `usuario_actual` es la dependencia de FastAPI que protege los endpoints: sin un token
  válido responde 401.
"""

import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from db.models import User
from db.repositories import UserRepository, UsernameTakenError

repositorio = UserRepository()

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 600_000

_bearer = HTTPBearer(auto_error=False)


class CredencialesInvalidas(Exception):
    """Usuario inexistente o contraseña incorrecta (no se distingue a propósito)."""


class UsuarioYaExiste(Exception):
    pass


def hashear_password(password: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), ITERACIONES).hex()
    return f"{ALGORITMO}${ITERACIONES}${sal}${digest}"


def verificar_password(password: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, digest = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != ALGORITMO:
        return False
    calculado = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), int(iteraciones)).hex()
    return hmac.compare_digest(calculado, digest)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# Hash de una contraseña cualquiera: si el usuario no existe se verifica contra él igualmente,
# para que la respuesta tarde lo mismo y no delate qué usuarios existen.
_HASH_FALSO = hashear_password(secrets.token_hex(8))


def registrar(username: str, password: str) -> User:
    try:
        return repositorio.create(username, hashear_password(password))
    except UsernameTakenError as exc:
        raise UsuarioYaExiste(username) from exc


def iniciar_sesion(username: str, password: str) -> tuple[str, User]:
    """Comprueba las credenciales y abre una sesión. Devuelve (token, usuario)."""
    usuario = repositorio.get_by_username(username)
    if not verificar_password(password, usuario.password_hash if usuario else _HASH_FALSO) or usuario is None:
        raise CredencialesInvalidas()

    token = secrets.token_urlsafe(32)
    repositorio.set_token(usuario, _hash_token(token), settings.session_ttl_hours)
    return token, usuario


def cerrar_sesion(token: str) -> None:
    repositorio.clear_token(_hash_token(token))


def token_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    """Dependencia de FastAPI: el token de la cabecera Authorization, o 401 si no viene."""
    if credenciales is None or not credenciales.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inicia sesión para continuar",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credenciales.credentials


def usuario_actual(token: str = Depends(token_actual)) -> User:
    """Dependencia de FastAPI: el usuario de la sesión, o 401 si el token falta, no existe o caducó
    (también si se ha iniciado sesión con ese usuario en otro navegador)."""
    usuario = repositorio.get_by_token(_hash_token(token))
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha caducado o se ha iniciado en otro dispositivo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario
