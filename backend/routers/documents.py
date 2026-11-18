"""Documentos técnicos. GET /api/documents lista los indexados; la subida (POST) sigue pendiente (501)."""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from models.schemas import DocumentsListResponse, TechnicalDocument
from services.documentos import listar_documentos, ruta_pdf

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentsListResponse)
def list_documents():
    """Listar la documentación indexada."""
    return {"documents": listar_documentos()}


@router.get("/documents/{filename}/file")
def get_document_file(filename: str):
    """Devolver el PDF para abrirlo en el navegador (inline = se muestra, no se descarga)."""
    ruta = ruta_pdf(filename)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return FileResponse(ruta, media_type="application/pdf", filename=ruta.name, content_disposition_type="inline")


@router.post("/documents", response_model=TechnicalDocument)
def upload_document(file: UploadFile):
    """Subir un PDF para indexarlo."""
    raise HTTPException(status_code=501, detail="Not implemented yet")