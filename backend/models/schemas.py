"""Modelos Pydantic del contrato API (ver docs/API_CONTRACT.md)."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvidenceStatus(str, Enum):
    high = "high"
    medium = "medium"
    insufficient = "insufficient"


class SourceType(str, Enum):
    """Tipo de documento: lo comparten las fuentes citadas y los documentos indexados."""

    manual = "manual"
    dtc_catalog = "dtc_catalog"
    decision_tree = "decision_tree"
    historical_case = "historical_case"
    safety_manual = "safety_manual"
    glossary = "glossary"


class Profile(str, Enum):
    mechanic = "mechanic"
    user = "user"


class DocumentStatus(str, Enum):
    processed = "processed"
    pending = "pending"
    failed = "failed"


# --- Chat -------------------------------------------------------------------


Role = Literal["user", "assistant"]


class HistoryItem(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    message: str
    engine_version: str = ""
    profile: Profile  # obligatorio: sin tipo de usuario la petición se rechaza (422)
    history: list[HistoryItem] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El mensaje no puede estar vacío")
        return value


class MessageResponse(BaseModel):
    id: str
    content: str


class Source(BaseModel):
    id: str
    document: str
    source_type: SourceType
    section: str | None = None
    page: int | None = None
    engine_version: str | None = None
    excerpt: str | None = None


class ChatResponse(BaseModel):
    message: MessageResponse
    evidence_status: EvidenceStatus | None = None
    needs_clarification: bool = False
    documents_consulted: int | None = None
    sources: list[Source] | None = None


# --- Versiones --------------------------------------------------------------


class VersionsResponse(BaseModel):
    versions: list[str]


# --- Documentos -------------------------------------------------------------


class TechnicalDocument(BaseModel):
    id: str
    filename: str
    type: SourceType
    engine_version: str
    pages: int
    uploaded_at: str
    status: DocumentStatus


class DocumentsListResponse(BaseModel):
    documents: list[TechnicalDocument] = Field(default_factory=list)


# --- Conversaciones ---------------------------------------------------------


class ConversationMessage(BaseModel):
    id: str
    role: Role
    content: str
    created_at: str | None = None
    response: dict | None = None


class Conversation(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    favorite: bool = False
    engine_version: str = ""
    # Vacío mientras el usuario aún no ha elegido tipo de usuario (conversación sin mensajes).
    profile: Profile | Literal[""] = ""
    messages: list[ConversationMessage] = Field(default_factory=list)


class ConversationsListResponse(BaseModel):
    conversations: list[Conversation] = Field(default_factory=list)
