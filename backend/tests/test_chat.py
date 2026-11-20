from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from models.schemas import ChatRequest, Profile
from routers import chat as chat_router


class FakeConversationRepository:
    def __init__(self):
        self.exchanges = {}
        self.used_ids = set()

    def exists_for_other_user(self, _user, _conversation_id):
        return False

    def find_exchange(self, _user, conversation_id, question_id):
        return self.exchanges.get((conversation_id, question_id))

    def message_id_taken(self, message_id):
        return message_id in self.used_ids

    def recent_history(self, _user, _conversation_id, _limit):
        return []

    def add_exchange(self, _user, conversation_id, version, profile, question, answer):
        conversation = {
            "id": conversation_id,
            "title": question.content[:50],
            "messages": [
                {"id": question.id, "role": "user", "content": question.content},
                {"id": answer.id, "role": "assistant", "content": answer.content},
            ],
        }
        saved_answer = {
            "id": answer.id,
            "content": answer.content,
            "response": answer.response,
        }
        self.exchanges[(conversation_id, question.id)] = (conversation, saved_answer)
        self.used_ids.update((question.id, answer.id))
        return conversation


def construir_peticion():
    return ChatRequest(
        conversation_id=uuid4(),
        message_id=uuid4(),
        message="¿Qué significa HTM-0142?",
        engine_version="V2.0",
        profile=Profile.mechanic,
    )


def test_guarda_y_registra_una_consulta_solo_una_vez(monkeypatch):
    repositorio = FakeConversationRepository()
    registros = []
    llamadas_rag = []
    monkeypatch.setattr(chat_router, "conversaciones", repositorio)
    monkeypatch.setattr(chat_router.registro, "registrar_consulta", lambda *a, **kw: registros.append((a, kw)))
    monkeypatch.setattr(chat_router.rag_pipeline, "armar_respuesta", lambda *a: (
        llamadas_rag.append(a) or {
            "message": {"id": str(uuid4()), "content": "Respuesta de prueba"},
            "evidence_status": "high",
            "sources": [],
            "documents_consulted": 0,
        }
    ))
    chat_router._canceladas.clear()
    peticion = construir_peticion()
    usuario = SimpleNamespace(id=9)

    primera = chat_router.chat(peticion, usuario)
    segunda = chat_router.chat(peticion, usuario)

    assert primera["message"]["content"] == "Respuesta de prueba"
    assert segunda["message"]["content"] == "Respuesta de prueba"
    assert len(llamadas_rag) == 1
    assert len(registros) == 1
    assert registros[0][1]["estado"] == "completada"
    assert registros[0][1]["user_id"] == 9


def test_registra_el_error_del_pipeline_y_devuelve_http_500(monkeypatch):
    repositorio = FakeConversationRepository()
    registros = []
    monkeypatch.setattr(chat_router, "conversaciones", repositorio)
    monkeypatch.setattr(chat_router.registro, "registrar_consulta", lambda *a, **kw: registros.append(kw))

    def falla(*_args):
        raise RuntimeError("fallo interno que no debe exponerse")

    monkeypatch.setattr(chat_router.rag_pipeline, "armar_respuesta", falla)
    chat_router._canceladas.clear()

    with pytest.raises(HTTPException) as error:
        chat_router.chat(construir_peticion(), SimpleNamespace(id=9))

    assert error.value.status_code == 500
    assert len(registros) == 1
    assert registros[0]["estado"] == "error"
    assert registros[0]["error"] == "RuntimeError"


def test_registra_error_si_falla_la_persistencia(monkeypatch):
    repositorio = FakeConversationRepository()
    registros = []
    monkeypatch.setattr(chat_router, "conversaciones", repositorio)
    monkeypatch.setattr(chat_router.registro, "registrar_consulta", lambda *a, **kw: registros.append(kw))
    monkeypatch.setattr(chat_router.rag_pipeline, "armar_respuesta", lambda *_: {
        "message": {"id": str(uuid4()), "content": "Respuesta de prueba"},
        "evidence_status": "high",
        "sources": [],
        "documents_consulted": 0,
    })

    def falla_guardado(*_args, **_kwargs):
        raise RuntimeError("detalle interno que no debe llegar al cliente")

    monkeypatch.setattr(repositorio, "add_exchange", falla_guardado)
    chat_router._canceladas.clear()

    with pytest.raises(HTTPException) as error:
        chat_router.chat(construir_peticion(), SimpleNamespace(id=9))

    assert error.value.status_code == 500
    assert error.value.detail == "No se pudo guardar la conversación"
    assert len(registros) == 1
    assert registros[0]["estado"] == "error_persistencia"
    assert registros[0]["error"] == "RuntimeError"
