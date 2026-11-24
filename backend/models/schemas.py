"""Modelos Pydantic del contrato de la API (los endpoints están en routers/)."""

import re
from enum import Enum
from typing import Literal
from uuid import UUID

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


class ChatRequest(BaseModel):
    # UUID que genera el frontend al empezar un chat. Si aún no existe, la conversación se crea
    # con la primera pregunta. El historial lo lee el backend de la BD: el cliente no lo envía.
    conversation_id: UUID
    # Id de la pregunta, generado por el frontend. Si se reenvía la misma pregunta (reintento tras
    # cancelar o perder la conexión) y ya estaba respondida, se devuelve lo guardado sin duplicarla.
    message_id: UUID
    message: str
    engine_version: str = ""
    profile: Profile  # obligatorio: sin tipo de usuario la petición se rechaza (422)

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
    # "cited": declarada por el modelo; "verified": cita literal validada por el backend; "retrieved": contexto.
    citation_status: Literal["cited", "verified", "retrieved"] = "retrieved"


class StepFragment(BaseModel):
    """Fragmento recuperado durante la búsqueda y si se usó en la respuesta."""

    document: str
    source_type: SourceType
    page: int | None = None
    section: str | None = None
    score: float
    used: bool


class StepPoint(BaseModel):
    """Resumen breve de una comprobación y las referencias documentales que la respaldan."""

    text: str
    refs: list[str] | None = None


class QueryStage(BaseModel):
    """Etapa observable de transformación de la consulta."""

    label: str
    text: str
    terms: list[str] | None = None
    note: str | None = None


class ReasoningStep(BaseModel):
    """Fase observable del proceso RAG, no una transcripción del razonamiento interno del modelo."""

    kind: Literal["query", "interpretation", "search", "analysis", "conclusion"]
    title: str
    detail: str | None = None
    stages: list[QueryStage] | None = None
    terms: list[str] | None = None
    fragments: list[StepFragment] | None = None
    points: list[StepPoint] | None = None
    evidence: EvidenceStatus | None = None


class SafetyAlert(BaseModel):
    """Aviso determinista de seguridad, independiente del texto generado por el LLM."""

    code: Literal["real_vehicle", "high_voltage", "engine_overheating"]
    severity: Literal["warning", "critical"]
    title: str
    message: str


class ClaimCheck(BaseModel):
    """Resultado de revisión orientativa de una afirmación factual."""

    claim: str
    status: Literal["supported", "conflicting", "not_found", "uncertain", "unverified"]
    source_ids: list[str] = Field(default_factory=list)
    evidence_excerpt: str | None = None


class ClaimVerification(BaseModel):
    """Resumen de la segunda pasada de revisión frente al contexto documental."""

    status: Literal["reviewed", "needs_review", "unavailable", "no_claims", "not_run"]
    claims_total: int = 0
    claims_supported: int = 0
    claims: list[ClaimCheck] = Field(default_factory=list)
    # True cuando el backend limitó el texto final a afirmaciones con cita literal validada.
    answer_restricted: bool = False


class RequestedEvidenceItem(BaseModel):
    """Un dato solicitado y el respaldo documental localizado para él."""

    item: str
    status: Literal["supported", "not_found", "uncertain", "conflicting"]
    source_ids: list[str] = Field(default_factory=list)
    evidence_excerpt: str | None = None


class EvidenceSufficiency(BaseModel):
    """Resultado de la comprobación previa de cobertura documental (R07)."""

    status: Literal["sufficient", "partial", "insufficient", "unavailable", "not_run"]
    requested_items: list[RequestedEvidenceItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class AnswerMeta(BaseModel):
    """La respuesta del asistente sin el texto: se guarda junto a cada mensaje del asistente."""

    evidence_status: EvidenceStatus | None = None
    needs_clarification: bool = False
    clarification_kind: Literal["engine_version", "technical", "version_mismatch", "version_comparison"] | None = None
    documents_consulted: int | None = None
    sources: list[Source] | None = None
    # Avisos calculados por el backend a partir de señales del mensaje, no del prompt/LLM.
    safety_alerts: list[SafetyAlert] = Field(default_factory=list)
    # Revisión orientativa de las afirmaciones frente a los fragmentos recuperados.
    claim_verification: ClaimVerification | None = None
    # Evaluación previa: distingue relevancia de los fragmentos y cobertura real de la pregunta.
    evidence_sufficiency: EvidenceSufficiency | None = None
    # Pasos observables del proceso RAG (compatibles con mensajes antiguos en texto plano).
    steps: list[ReasoningStep | str] | None = None


class ChatResponse(AnswerMeta):
    message: MessageResponse
    # La conversación ya guardada (con la pregunta y esta respuesta): el frontend la sustituye tal cual.
    conversation: "ConversationOut"


# --- Conversaciones -----------------------------------------------------------


class StoredMessage(BaseModel):
    id: str
    role: Role
    content: str
    created_at: str
    # Versión y perfil con los que se hizo esta pregunta (o para los que se respondió).
    engine_version: str = ""
    profile: Profile | Literal[""] = ""
    response: AnswerMeta | None = None


class ConversationOut(BaseModel):
    """`engine_version` y `profile` son los últimos usados: el chat se reanuda con ellos."""

    id: str
    title: str
    created_at: str
    updated_at: str
    favorite: bool
    engine_version: str
    profile: Profile | Literal[""]
    messages: list[StoredMessage]


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationOut]


class ConversationUpdate(BaseModel):
    """Cambios parciales: solo se aplican los campos que vienen."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    favorite: bool | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("El título no puede estar vacío")
        return value


# --- Usuarios -----------------------------------------------------------------

# De 3 a 50 caracteres y sin espacios (vale un nombre o un correo).
USERNAME_PATTERN = re.compile(r"^\S{3,50}$")


class Credentials(BaseModel):
    username: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        # Sin distinción de mayúsculas: "Pepe" y "pepe" son el mismo usuario.
        return value.strip().lower()


class RegisterRequest(Credentials):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _valid_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError("El usuario debe tener entre 3 y 50 caracteres y no puede tener espacios")
        return value


class UserOut(BaseModel):
    id: int
    username: str
    created_at: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


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


# ChatResponse usa ConversationOut antes de que se defina.
ChatResponse.model_rebuild()
