from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    """Obtener fragmento o URL de una fuente citada."""
    # TODO: recuperar fragmento por id
    _ = source_id
    raise HTTPException(status_code=501, detail="Not implemented yet")
