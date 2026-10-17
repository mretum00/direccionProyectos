"""Modelos Pydantic del contrato API (v1.0.0). La lógica de negocio irá en los controladores."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class EvidenceStatus(str, Enum):
    high = "high"
    medium = "medium"
    insufficient = "insufficient"


class Criticality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SafetyLevel(str, Enum):
    warning = "warning"
    critical = "critical"


class SourceType(str, Enum):
    manual = "manual"
    dtc_catalog = "dtc_catalog"
    decision_tree = "decision_tree"
    historical_case = "historical_case"
    safety_manual = "safety_manual"
    glossary = "glossary"


class Profile(str, Enum):
    mechanic = "mechanic"
    user = "user"


class DiscardReason(str, Enum):
    obsolete_version = "obsolete_version"
    version_mismatch = "version_mismatch"


class DocumentType(str, Enum):
    manual = "manual"
    dtc_catalog = "dtc_catalog"
    decision_tree = "decision_tree"
    historical_case = "historical_case"
    safety_manual = "safety_manual"
    glossary = "glossary"


class DocumentStatus(str, Enum):
    processed = "processed"
    pending = "pending"
    failed = "failed"


class HistoryItem(BaseModel):
    role: str
    content: str


class VehicleInfo(BaseModel):
    brand: str = ""
    model: str = ""
    year: Optional[int] = None
    vin: str = ""


class ChatRequest(BaseModel):
    conversation_id: str = ""
    message: str
    engine: str = ""
    engine_version: str = ""
    system: Optional[str] = None
    profile: Profile = Profile.mechanic
    history: List[HistoryItem] = Field(default_factory=list)
    vehicle: VehicleInfo = Field(default_factory=VehicleInfo)

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


class SafetyItem(BaseModel):
    level: SafetyLevel
    text: str


class ClarificationField(BaseModel):
    key: str
    label: str
    options: Optional[List[str]] = None


class Clarification(BaseModel):
    message: str = ""
    missing_fields: List[ClarificationField] = Field(default_factory=list)


class InterpretedQuery(BaseModel):
    original: str
    technical_terms: List[str] = Field(default_factory=list)


class DetectedDTC(BaseModel):
    code: str
    description: str


class ResponseSections(BaseModel):
    diagnosis: Optional[str] = None
    possible_causes: Optional[List[str]] = None
    criticality: Optional[Criticality] = None
    safety: Optional[List[SafetyItem]] = None
    ppe: Optional[List[str]] = None
    checks: Optional[List[str]] = None
    decision_tree_id: Optional[str] = None
    procedure: Optional[str] = None


class Source(BaseModel):
    id: str
    document: str
    source_type: SourceType
    section: Optional[str] = None
    page: Optional[int] = None
    engine: Optional[str] = None
    engine_version: Optional[str] = None
    system: Optional[str] = None
    excerpt: Optional[str] = None
    url: Optional[str] = None


class DiscardedSource(BaseModel):
    document: str
    reason: DiscardReason
    detail: Optional[str] = None


class ChatResponse(BaseModel):
    message: MessageResponse
    evidence_status: Optional[EvidenceStatus] = None
    needs_clarification: Optional[bool] = False
    confidence: Optional[float] = None
    documents_consulted: Optional[int] = None
    interpreted_query: Optional[InterpretedQuery] = None
    detected_dtc: Optional[List[DetectedDTC]] = None
    sections: Optional[ResponseSections] = None
    clarification: Optional[Clarification] = None
    sources: Optional[List[Source]] = None
    discarded_sources: Optional[List[DiscardedSource]] = None


class TechnicalDocument(BaseModel):
    id: str
    filename: str
    type: DocumentType
    engine: str
    engine_version: str
    pages: int
    uploaded_at: str
    status: DocumentStatus


class DocumentsListResponse(BaseModel):
    documents: List[TechnicalDocument] = Field(default_factory=list)


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
    system: Optional[str] = None
    profile: Profile = Profile.mechanic
    messages: List[ConversationMessage] = Field(default_factory=list)
