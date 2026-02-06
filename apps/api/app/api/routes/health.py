"""
健康检查与系统诊断
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.services.layer_factory.comfyui_client import get_comfyui_client

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("")
async def health_check():
    """基本健康检查 (K8s liveness probe)"""
    return {"status": "healthy"}

@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """详细系统诊断 (Database, Redis, ComfyUI, LLM config)"""
    status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "minio": "unknown",
        "comfyui": "unknown",
        "llm_config": "unknown"
    }
    
    # 1. Check Database
    try:
        db.execute(text("SELECT 1"))
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # 2. Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        status["redis"] = "connected"
    except Exception as e:
        status["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # 3. Check ComfyUI
    if settings.COMFYUI_URL:
        client = get_comfyui_client()
        try:
            # Check system stats using raw httpx if client doesn't expose quick health
            # Re-using logic from client.check_health if available, or manual check
            if hasattr(client, "check_health"):
                is_healthy = await client.check_health()
                status["comfyui"] = "connected" if is_healthy else "unreachable"
            else:
                 status["comfyui"] = "client_check_not_implemented"
        except Exception as e:
            status["comfyui"] = f"error: {str(e)}"
    else:
        status["comfyui"] = "mock_mode"

    # 4. Check LLM Config
    status["llm_config"] = {
        "provider": settings.LLM_PROVIDER,
        "base_url": settings.LLM_BASE_URL or "(default)",
        "model": settings.LLM_MODEL,
        "has_key": bool(settings.LLM_API_KEY)
    }

    return status
