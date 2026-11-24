"""Errores tipados y mensajes seguros para fallos del proveedor de IA."""

from __future__ import annotations


class LLMServiceError(RuntimeError):
    """Fallo conocido al utilizar el servicio de lenguaje.

    `code` sirve para el registro interno; `user_message` es el único detalle que
    debe exponerse al cliente. Nunca se propaga el mensaje original del proveedor.
    """

    def __init__(
        self,
        code: str,
        user_message: str,
        *,
        http_status: int = 503,
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message
        self.http_status = http_status
        self.retryable = retryable


def clasificar_error_groq(error: Exception) -> LLMServiceError:
    """Convierte las excepciones habituales de Groq en errores controlados."""
    nombre = type(error).__name__
    estado = getattr(error, "status_code", None)

    if nombre == "RateLimitError" or estado == 429:
        return LLMServiceError(
            "rate_limit",
            "El servicio de IA está recibiendo demasiadas solicitudes. Espera un momento e inténtalo de nuevo.",
            http_status=429,
            retryable=True,
        )

    if nombre in {"APITimeoutError", "APIConnectionTimeoutError", "TimeoutError"} or estado == 408:
        return LLMServiceError(
            "provider_timeout",
            "El servicio de IA ha tardado demasiado en responder. Inténtalo de nuevo.",
            retryable=True,
        )

    if nombre in {"APIConnectionError", "ConnectError", "ConnectionError"}:
        return LLMServiceError(
            "provider_connection",
            "No se ha podido conectar con el servicio de IA. Comprueba la conexión e inténtalo de nuevo.",
            retryable=True,
        )

    if nombre in {"AuthenticationError", "PermissionDeniedError"} or estado in {401, 403}:
        return LLMServiceError(
            "provider_authentication",
            "El servicio de IA no está disponible por un problema de configuración. Contacta con el administrador.",
        )

    if nombre in {"InternalServerError", "ServiceUnavailableError"} or (
        isinstance(estado, int) and estado >= 500
    ):
        return LLMServiceError(
            "provider_unavailable",
            "El servicio de IA no está disponible temporalmente. Inténtalo de nuevo más tarde.",
            retryable=True,
        )

    if nombre == "ModuleNotFoundError":
        return LLMServiceError(
            "provider_dependency_missing",
            "El servicio de IA no está configurado correctamente. Contacta con el administrador.",
        )

    return LLMServiceError(
        "provider_error",
        "No se ha podido completar la consulta con el servicio de IA. Inténtalo de nuevo.",
        http_status=502,
        retryable=False,
    )
