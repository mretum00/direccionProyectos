from fastapi import APIRouter

from config import APP_VERSION, settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    """Comprobar que el backend está en marcha y que la base de datos vectorial existe."""
    database_ready = settings.db_path.is_file()
    return {
        "status": "ok" if database_ready else "degraded",
        "version": APP_VERSION,
        "database": database_ready,
        "llm_configured": bool(settings.groq_api_key),
    }
