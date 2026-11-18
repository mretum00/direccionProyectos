"""GET /api/versions: versiones del sistema que admite el backend (las ofrece el selector del frontend)."""

from fastapi import APIRouter

from config import ENGINE_VERSIONS
from models.schemas import VersionsResponse

router = APIRouter(prefix="/api", tags=["versions"])


@router.get("/versions", response_model=VersionsResponse)
def list_versions():
    return {"versions": list(ENGINE_VERSIONS)}
