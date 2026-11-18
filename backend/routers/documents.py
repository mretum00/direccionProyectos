"""Documentos técnicos. GET /api/documents lista los indexados; la subida (POST) sigue pendiente (501)."""

from fastapi import APIRouter, HTTPException, UploadFile

from models.schemas import DocumentsListResponse, TechnicalDocument
from services.documentos import listar_documentos

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentsListResponse)
def list_documents():
    """Listar la documentación indexada."""
    return {"documents": listar_documentos()}


@router.post("/documents", response_model=TechnicalDocument)
def upload_document(file: UploadFile):
    """Subir un PDF para indexarlo."""
    raise HTTPException(status_code=501, detail="Not implemented yet")