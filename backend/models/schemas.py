"""Modelos Pydantic del contrato API (ver docs/API_CONTRACT.md)."""

from enum import Enum
from typing import List, Optional

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


class HistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: str = ""
    message: str
    engine: str = ""
    engine_version: str = ""
    profile: Profile = Profile.mechanic
    history: List[HistoryItem] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El mensaje no puede estar vacío")
        return value

    @field_validator("engine", "engine_version")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class MessageResponse(BaseModel):
    id: str
    role: str = "assistant"
    content: str


class ClarificationField(BaseModel):
    key: str
    label: str
    options: Optional[List[str]] = None


class Clarification(BaseModel):
    message: str = ""
    missing_fields: List[ClarificationField] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    document: str
    source_type: SourceType
    section: Optional[str] = None
    page: Optional[int] = None
    engine: Optional[str] = None
    engine_version: Optional[str] = None
    excerpt: Optional[str] = None
    url: Optional[str] = None


class ChatResponse(BaseModel):
    message: MessageResponse
    evidence_status: Optional[EvidenceStatus] = None
    needs_clarification: bool = False
    documents_consulted: Optional[int] = None
    clarification: Optional[Clarification] = None
    sources: Optional[List[Source]] = None


# --- Documentos -------------------------------------------------------------


class TechnicalDocument(BaseModel):
    id: str
    filename: str
    type: SourceType
    engine: str
    engine_version: str
    pages: int
    uploaded_at: str
    status: DocumentStatus


class DocumentsListResponse(BaseModel):
    documents: List[TechnicalDocument] = Field(default_factory=list)


# --- Conversaciones ---------------------------------------------------------


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: Optional[str] = None
    response: Optional[dict] = None


class Conversation(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    favorite: bool = False
    engine: str = ""
    engine_version: str = ""
    profile: Profile = Profile.mechanic
    messages: List[ConversationMessage] = Field(default_factory=list)


class ConversationsListResponse(BaseModel):
    conversations: List[Conversation] = Field(default_factory=list)
