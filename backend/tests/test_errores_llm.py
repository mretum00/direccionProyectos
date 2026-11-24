"""Pruebas de clasificación de errores del proveedor de IA."""

from services.errores_llm import LLMServiceError, clasificar_error_groq


class RateLimitError(Exception):
    status_code = 429


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


class AuthenticationError(Exception):
    status_code = 401


class InternalServerError(Exception):
    status_code = 503


def test_limite_de_peticion_se_identifica_como_reintentable():
    error = clasificar_error_groq(RateLimitError("detalle privado"))

    assert isinstance(error, LLMServiceError)
    assert error.code == "rate_limit"
    assert error.http_status == 429
    assert error.retryable is True
    assert "demasiadas solicitudes" in error.user_message
    assert "detalle privado" not in error.user_message


def test_timeout_y_conexion_se_identifican_como_transitorios():
    timeout = clasificar_error_groq(APITimeoutError())
    conexion = clasificar_error_groq(APIConnectionError())

    assert timeout.code == "provider_timeout"
    assert timeout.http_status == 503
    assert timeout.retryable is True
    assert conexion.code == "provider_connection"
    assert conexion.retryable is True


def test_clave_o_permisos_invalidos_no_se_marcan_reintentables():
    error = clasificar_error_groq(AuthenticationError("credenciales privadas"))

    assert error.code == "provider_authentication"
    assert error.http_status == 503
    assert error.retryable is False
    assert "credenciales privadas" not in error.user_message


def test_error_interno_del_proveedor_es_temporal():
    error = clasificar_error_groq(InternalServerError())

    assert error.code == "provider_unavailable"
    assert error.http_status == 503
    assert error.retryable is True


def test_error_desconocido_no_filtra_el_detalle_original():
    error = clasificar_error_groq(ValueError("secreto o traza interna"))

    assert error.code == "provider_error"
    assert error.http_status == 502
    assert "secreto o traza interna" not in error.user_message
