"""
Media URL endpoint — generates fresh presigned URLs for MinIO storage keys.
"""
from fastapi import APIRouter, HTTPException, Query

from app.core.storage import get_storage_client

router = APIRouter()

ALLOWED_PREFIXES = (
    "generated/",
    "panels/",
    "exports/",
    "assets/",
    "agent-commit/",
    "agent_commit/",
)


@router.get("/media/url")
def get_media_url(
    key: str = Query(..., description="MinIO storage key"),
    expires: int = Query(3600, ge=60, le=86400, description="URL expiry in seconds"),
):
    """
    Generate a fresh presigned URL for a MinIO storage key.

    Returns:
        {"url": "http://...", "expires_in": 3600}
    """
    if not any(key.startswith(p) for p in ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail=f"Invalid storage key prefix. Allowed: {ALLOWED_PREFIXES}")

    storage = get_storage_client()
    if not storage.available:
        raise HTTPException(status_code=503, detail="Storage service unavailable")

    if not storage.exists(key):
        raise HTTPException(status_code=404, detail="File not found in storage")

    url = storage.get_url(key, expires=expires)
    return {"url": url, "expires_in": expires}
