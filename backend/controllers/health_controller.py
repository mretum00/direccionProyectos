from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    """Comprobar que el backend está en marcha."""
    # TODO: añadir comprobaciones reales (BD, embeddings, etc.)
    return {"status": "ok", "version": "1.0.0"}
