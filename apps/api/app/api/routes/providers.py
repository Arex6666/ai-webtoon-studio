"""
Provider API Routes - Provider 状态和健康检查

提供 Provider 可用性检查接口，供前端显示状态
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import time
import logging

from app.core.config import settings
from app.services.video import get_video_provider, list_providers as list_video_providers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/providers", tags=["Providers"])


class ProviderStatus(BaseModel):
    """Provider 状态"""
    name: str
    type: str  # 'image' | 'video'
    available: bool
    configured: bool
    models: List[str] = []


class ProviderListResponse(BaseModel):
    """Provider 列表响应"""
    providers: List[ProviderStatus]


class ProviderHealthResponse(BaseModel):
    """健康检查响应"""
    name: str
    healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class RecommendedProviderResponse(BaseModel):
    """推荐 Provider 响应"""
    provider: str
    reason: str


# Provider 配置信息
IMAGE_PROVIDERS = [
    {
        "name": "comfyui",
        "models": ["flux", "sd15", "sdxl"],
        "config_key": "COMFYUI_URL",
    },
    {
        "name": "tongyi",
        "models": ["wanx2.0-t2i-turbo", "wanx-v1"],
        "config_key": "TONGYI_API_KEY",
    },
    {
        "name": "doubao",
        "models": ["jimeng-xl", "jimeng-i2i"],
        "config_key": "DOUBAO_API_KEY",
    },
]

VIDEO_PROVIDERS = [
    {
        "name": "tongyi",
        "models": ["wanx2.1-i2v-plus"],
        "config_key": "TONGYI_API_KEY",
    },
    {
        "name": "doubao",
        "models": ["jimeng-video"],
        "config_key": "DOUBAO_API_KEY",
    },
    {
        "name": "comfyui",
        "models": ["animatediff"],
        "config_key": "COMFYUI_URL",
    },
]


def is_configured(config_key: str) -> bool:
    """检查配置是否已设置"""
    value = getattr(settings, config_key, None)
    return bool(value)


@router.get("", response_model=ProviderListResponse)
async def list_providers():
    """
    获取所有可用的 Provider 列表
    
    返回每个 Provider 的配置状态和可用模型
    """
    providers = []
    
    # Image providers
    for p in IMAGE_PROVIDERS:
        configured = is_configured(p["config_key"])
        providers.append(ProviderStatus(
            name=p["name"],
            type="image",
            available=configured,
            configured=configured,
            models=p["models"] if configured else [],
        ))
    
    # Video providers
    for p in VIDEO_PROVIDERS:
        configured = is_configured(p["config_key"])
        # 对于视频，检查实际注册的 provider
        video_provider = get_video_provider(p["name"])
        available = video_provider is not None
        
        providers.append(ProviderStatus(
            name=p["name"],
            type="video",
            available=available,
            configured=configured,
            models=p["models"] if available else [],
        ))
    
    return ProviderListResponse(providers=providers)


@router.get("/{provider_name}/health", response_model=ProviderHealthResponse)
async def check_provider_health(provider_name: str):
    """
    检查特定 Provider 的健康状态
    
    执行实际的 API 连通性检查
    """
    start_time = time.time()
    
    try:
        # 查找 provider
        provider = get_video_provider(provider_name)
        
        if provider is None:
            # 尝试查找图片 provider
            from app.services.layer_factory.tongyi_image_provider import get_tongyi_image_provider
            from app.services.layer_factory.doubao_image_provider import get_doubao_image_provider
            
            if provider_name == "tongyi":
                provider = get_tongyi_image_provider()
            elif provider_name == "doubao":
                provider = get_doubao_image_provider()
            elif provider_name == "comfyui":
                from app.services.layer_factory.comfyui_client import get_comfyui_client
                client = get_comfyui_client()
                healthy = await client.health_check() if hasattr(client, 'health_check') else True
                latency = int((time.time() - start_time) * 1000)
                return ProviderHealthResponse(
                    name=provider_name,
                    healthy=healthy,
                    latency_ms=latency,
                )
        
        if provider is None:
            return ProviderHealthResponse(
                name=provider_name,
                healthy=False,
                error="Provider not configured",
            )
        
        # 执行健康检查
        healthy = await provider.check_health()
        latency = int((time.time() - start_time) * 1000)
        
        return ProviderHealthResponse(
            name=provider_name,
            healthy=healthy,
            latency_ms=latency if healthy else None,
        )
        
    except Exception as e:
        logger.error(f"Health check failed for {provider_name}: {e}")
        return ProviderHealthResponse(
            name=provider_name,
            healthy=False,
            error=str(e),
        )


@router.get("/recommended", response_model=RecommendedProviderResponse)
async def get_recommended_provider(type: str = "image"):
    """
    获取推荐的 Provider
    
    按优先级返回第一个可用的 Provider:
    - Image: comfyui > tongyi > doubao
    - Video: tongyi > doubao > comfyui
    """
    if type == "image":
        priority = ["comfyui", "tongyi", "doubao"]
        providers_config = IMAGE_PROVIDERS
    else:
        priority = ["tongyi", "doubao", "comfyui"]
        providers_config = VIDEO_PROVIDERS
    
    for name in priority:
        config = next((p for p in providers_config if p["name"] == name), None)
        if config and is_configured(config["config_key"]):
            reason = f"{name} is configured and available"
            return RecommendedProviderResponse(provider=name, reason=reason)
    
    # 如果没有配置任何 provider，返回 mock
    return RecommendedProviderResponse(
        provider="mock",
        reason="No providers configured, using mock mode"
    )
