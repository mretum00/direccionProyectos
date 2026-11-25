"""Pruebas del presupuesto reducido y reintento acotado de R07 en Groq."""

from types import SimpleNamespace


def test_evaluacion_r07_reintenta_un_429_transitorio_y_limita_tokens(monkeypatch):
    from services import llm

    class RateLimitError(Exception):
        status_code = 429

    class Completions: 
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise RateLimitError("Please try again in 120ms")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"items": []}'))]
            )

    completions = Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    esperas = []
    monkeypatch.setattr(llm, "_obtener_cliente", lambda: client)
    monkeypatch.setattr(llm.time, "sleep", lambda segundos: esperas.append(segundos))

    resultado = llm._llamar_groq(
        "prompt de prueba",
        verificacion=True,
        max_completion_tokens_override=700,
        reasoning_effort_override="low",
    )

    assert resultado == '{"items": []}'
    assert len(completions.calls) == 2
    assert completions.calls[0]["max_completion_tokens"] == 700
    assert completions.calls[0]["reasoning_effort"] == "low"
    assert all(
        llamada["reasoning_effort"] in {"low", "medium", "high"}
        for llamada in completions.calls
    )
    assert esperas == [0.22]
