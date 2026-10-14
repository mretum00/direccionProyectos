"""
ARSOFT AI — Backend mock mínimo (FastAPI + Pydantic + CORS)
Ejemplo del contrato API para el equipo de backend.
No incluye lógica RAG, embeddings ni LLM — solo sirve como referencia del contrato.

Ejecutar:
  pip install fastapi uvicorn pydantic
  uvicorn main:app --reload --port 8000
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional, List
from enum import Enum

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="ARSOFT AI Backend Mock", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Enums ───

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


# ─── Chat models ───

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


# ─── Document models ───

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
    documents: List[TechnicalDocument]


# ─── Conversation models ───

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


# ─── Endpoints ───

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # TODO: Implementar RAG real
    # 1. Buscar fragmentos en SQLite + sqlite-vec filtrando por engine/engine_version
    # 2. Construir contexto con los fragmentos recuperados
    # 3. Enviar al LLM (Groq) con las instrucciones del profile
    # 4. Devolver respuesta estructurada con fuentes
    return ChatResponse(
        message=MessageResponse(
            id=str(uuid4()),
            content="Respuesta de ejemplo del backend mock. El backend real implementará RAG.",
        )
    )


@app.get("/api/documents", response_model=DocumentsListResponse)
async def list_documents():
    return DocumentsListResponse(documents=[])


@app.get("/api/sources/{source_id}")
async def get_source(source_id: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@app.get("/api/conversations")
async def list_conversations():
    return []


@app.post("/api/conversations")
async def save_conversation(conv: Conversation):
    return conv


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    raise HTTPException(status_code=404, detail="Not found")


@app.put("/api/conversations")
async def update_conversation(conv: Conversation):
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    return {"deleted": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
