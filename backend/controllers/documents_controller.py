from fastapi import APIRouter, HTTPException, UploadFile

from models.schemas import DocumentsListResponse, TechnicalDocument

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentsListResponse)
async def list_documents():
    """Listar documentación indexada."""
    # TODO: leer documentos desde la base de datos
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/documents", response_model=TechnicalDocument)
async def upload_document(file: UploadFile):
    """Subir un PDF para indexar."""
    # TODO: guardar archivo e indexar
    _ = file
    raise HTTPException(status_code=501, detail="Not implemented yet")
