"""
Chapter routes - split into sub-modules
"""
from fastapi import APIRouter

from app.api.routes.chapters import crud, revisions, studio, script, storyboard, automation

# Create main router
router = APIRouter(tags=["chapters"])

# Include all sub-routers with empty prefix
# The main.py includes this router with prefix="/api/v1/chapters"
router.include_router(crud.router, prefix="", tags=["chapters-crud"])
router.include_router(revisions.router, prefix="", tags=["chapters-revisions"])
router.include_router(studio.router, prefix="", tags=["chapters-studio"])
router.include_router(script.router, prefix="", tags=["chapters-script"])
router.include_router(storyboard.router, prefix="", tags=["chapters-storyboard"])
router.include_router(automation.router, prefix="", tags=["chapters-automation"])

# Re-export for backwards compatibility
__all__ = ["router"]
