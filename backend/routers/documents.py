"""Documentos técnicos. Pendiente de implementar: ambos endpoints responden 501."""

from fastapi import APIRouter, HTTPException, UploadFile

from models.schemas import DocumentsListResponse, TechnicalDocument

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentsListResponse)
def list_documents():
    """Listar la documentación indexada."""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/documents", response_model=TechnicalDocument)
def upload_document(file: UploadFile):
    """Subir un PDF para indexarlo."""
    raise HTTPException(status_code=501, detail="Not implemented yet")
