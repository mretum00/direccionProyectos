"""Usuarios: registro, inicio y cierre de sesión, y datos del usuario actual."""

from fastapi import APIRouter, Depends, HTTPException, status

from db.models import User
from models.schemas import Credentials, LoginResponse, RegisterRequest, UserOut
from services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, created_at=user.created_at)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    """Crea la cuenta. No inicia sesión: el frontend vuelve al formulario de acceso."""
    try:
        return _user_out(auth.registrar(body.username, body.password))
    except auth.UsuarioYaExiste as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese usuario ya existe") from exc


@router.post("/login", response_model=LoginResponse)
def login(body: Credentials):
    try:
        token, user = auth.iniciar_sesion(body.username, body.password)
    except auth.CredencialesInvalidas as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos"
        ) from exc
    return LoginResponse(token=token, user=_user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(auth.token_actual)):
    auth.cerrar_sesion(token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth.usuario_actual)):
    """Comprueba la sesión guardada en el navegador al abrir la app."""
    return _user_out(user)
