"""Documentos técnicos indexados: la lista (GET /api/documents) y el PDF de cada uno.

Los documentos se añaden regenerando la BD del RAG (backend/db/database_generator.py), no desde la app.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models.schemas import DocumentsListResponse
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
