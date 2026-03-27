"""
Doubao Image Provider - 豆包 Seedream 4.5 图片生成
基于火山引擎方舟大模型 API 实现，使用 API Key 认证

支持:
- 文生图 (text-to-image)
- 图生图 (image-to-image) - 需要传入 reference_image_url

注意: 火山引擎返回的图片 URL 是临时签名 URL，会过期
因此我们需要下载图片并保存到自己的存储 (MinIO)
"""
import httpx
import asyncio
import logging
import time
import json
import base64
import uuid
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.core.config import settings
from app.services.storage.media_persister import persist_media, persist_media_bytes, MediaPersistError

logger = logging.getLogger(__name__)


# Seedream 4.5 API 配置
SEEDREAM_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
SEEDREAM_MODEL = "doubao-seedream-4-5-251128"


@dataclass
class DoubaoImageRequest:
    """豆包图片生成请求"""
    prompt: str
    negative_prompt: str = ""
    
    # Seedream 4.5 最小像素要求: 3,686,400
    width: int = 1920
    height: int = 1920
    
    seed: Optional[int] = None
    
    # 参考图片 (URL 或 Base64)
    reference_image_url: Optional[str] = None
    
    # 引导系数 (1.0 - 10.0, 默认 2.5)
    guidance_scale: float = 2.5


@dataclass
class DoubaoImageResult:
    """豆包图片生成结果"""
    success: bool
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None
    
    seed: Optional[int] = None
    provider: str = "doubao"
    cost: float = 0.0
    generation_time_ms: int = 0
    
    error: Optional[str] = None
    error_code: Optional[str] = None


class DoubaoImageProvider:
    """
    豆包 Seedream 4.5 图片生成 Provider
    
    使用火山引擎方舟大模型 API，API Key 认证
    文档: https://www.volcengine.com/docs/82379/1541523
    """
    
    provider_name = "doubao"
    
    def __init__(self):
        # 支持两种 API Key 配置方式
        self.api_key = getattr(settings, 'DOUBAO_API_KEY', None) or getattr(settings, 'ARK_API_KEY', None)
        
        if not self.api_key:
            logger.warning("[DoubaoImage] No API Key configured (DOUBAO_API_KEY or ARK_API_KEY)")
        else:
            logger.info(f"[DoubaoImage] Initialized with API Key: {self.api_key[:15]}...")
        
            # httpx 不直接支持代理环境变量，需要显式配置
            # 但对于火山引擎的国内 API，通常不需要代理
        
        # 增加超时和重试配置
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=30.0),
            verify=True,  # SSL 验证
            follow_redirects=True,
        )

    
    async def generate(
        self,
        request: DoubaoImageRequest,
        progress_callback: Optional[callable] = None,
    ) -> DoubaoImageResult:
        """生成图片"""
        if not self.api_key:
            return DoubaoImageResult(
                success=False,
                error="DOUBAO_API_KEY 或 ARK_API_KEY 未配置",
                error_code="CONFIG_ERROR",
            )
        
        start_time = time.time()
        
        try:
            if progress_callback:
                progress_callback(0.1, "提交任务...")
            
            logger.info(f"[DoubaoImage] Generating with Seedream 4.5, prompt: {request.prompt[:80]}...")
            
            # Seedream 4.5 只支持 "2K" 或 "4K" 作为 size 参数
            # 通过 prompt 中描述宽高比来控制实际尺寸
            size_preset = "2K"  # 默认使用 2K (2048x2048 基准)
            
            # 根据请求的尺寸确定宽高比描述
            width = request.width or 1024
            height = request.height or 1024
            if width > height:
                aspect_hint = "horizontal, landscape orientation"
            elif height > width:
                aspect_hint = "vertical, portrait orientation"
            else:
                aspect_hint = "square"
            
            # 将宽高比提示添加到 prompt 中
            enhanced_prompt = f"{request.prompt}, {aspect_hint}"
            
            # 构建请求
            payload = {
                "model": SEEDREAM_MODEL,
                "prompt": enhanced_prompt,
                "size": size_preset,  # 只能是 "2K" 或 "4K"
                "response_format": "url",  # 返回 URL
            }
            
            # 可选参数
            if request.negative_prompt:
                payload["negative_prompt"] = request.negative_prompt
            
            if request.seed:
                payload["seed"] = request.seed
            
            if request.guidance_scale:
                payload["guidance_scale"] = request.guidance_scale
            
            # 参考图片 (图生图)
            if request.reference_image_url:
                # 如果是 URL，直接使用；如果是 Base64，需要添加前缀
                if request.reference_image_url.startswith("http"):
                    payload["image"] = request.reference_image_url
                else:
                    # 假设是 Base64
                    payload["image"] = request.reference_image_url
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            
            logger.info(f"[DoubaoImage] Calling Seedream 4.5 API: {SEEDREAM_API_URL}")
            logger.debug(f"[DoubaoImage] Payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
            
            if progress_callback:
                progress_callback(0.3, "正在生成...")
            
            # 使用 requests 同步库，在线程池中执行（避免 httpx 异步 TLS 问题）
            import requests
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            def sync_request():
                return requests.post(
                    SEEDREAM_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=180,
                )
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(executor, sync_request)
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[DoubaoImage] API error: {response.status_code} - {error_text[:500]}")
                return DoubaoImageResult(
                    success=False,
                    error=f"API error: {response.status_code} - {error_text[:200]}",
                    error_code=f"HTTP_{response.status_code}",
                )
            
            result_data = response.json()
            logger.info(f"[DoubaoImage] API response: {json.dumps(result_data, ensure_ascii=False)[:500]}")
            
            if progress_callback:
                progress_callback(0.9, "处理结果...")
            
            # 解析响应
            # Seedream 4.5 返回格式:
            # {
            #   "created": 1234567890,
            #   "data": [
            #     {"url": "https://..."},
            #     ...
            #   ]
            # }
            temp_image_url = None
            seed_used = None
            image_data = None
            
            if "data" in result_data and len(result_data["data"]) > 0:
                first_image = result_data["data"][0]
                temp_image_url = first_image.get("url")
                seed_used = first_image.get("seed")
                
                # 有些响应用 b64_json 而不是 url
                if not temp_image_url and first_image.get("b64_json"):
                    image_data = base64.b64decode(first_image["b64_json"])
                    logger.info("[DoubaoImage] Response contains b64_json, decoded to bytes")
            
            if not temp_image_url and not image_data:
                logger.error(f"[DoubaoImage] No image URL in response: {json.dumps(result_data, ensure_ascii=False)[:300]}")
                return DoubaoImageResult(
                    success=False,
                    error=f"No image URL in response",
                    error_code="NO_OUTPUT",
                )
            
            # ==== 持久化到 MinIO ====
            storage_key = None
            try:
                if image_data:
                    storage_key = await persist_media_bytes(image_data, "images", "image/jpeg")
                elif temp_image_url:
                    storage_key = await persist_media(temp_image_url, "images", "image/jpeg")
            except MediaPersistError as e:
                logger.warning(f"[DoubaoImage] Failed to persist image: {e}, using temp URL")

            generation_time = int((time.time() - start_time) * 1000)
            # Use storage key if persisted, otherwise fall back to temp URL
            result_url = storage_key or temp_image_url

            logger.info(f"[DoubaoImage] Success! URL/key: {result_url[:80]}...")

            return DoubaoImageResult(
                success=True,
                image_url=result_url,
                image_data=image_data,
                seed=seed_used,
                cost=0.1,
                generation_time_ms=generation_time,
            )
            
        except Exception as e:
            logger.error(f"[DoubaoImage] Generation failed: {e}", exc_info=True)
            return DoubaoImageResult(
                success=False,
                error=str(e),
                error_code="GENERATION_FAILED",
            )
    
    async def check_health(self) -> bool:
        """检查服务可用性"""
        return bool(self.api_key)


# 全局实例
_doubao_image_provider: Optional[DoubaoImageProvider] = None


def get_doubao_image_provider() -> Optional[DoubaoImageProvider]:
    """获取豆包图片 Provider"""
    global _doubao_image_provider
    if _doubao_image_provider is None:
        api_key = getattr(settings, 'DOUBAO_API_KEY', None) or getattr(settings, 'ARK_API_KEY', None)
        if api_key:
            logger.info(f"[DoubaoImage] Initializing Seedream 4.5 provider")
            _doubao_image_provider = DoubaoImageProvider()
        else:
            logger.warning(f"[DoubaoImage] Provider not initialized - no API Key configured")
    return _doubao_image_provider
