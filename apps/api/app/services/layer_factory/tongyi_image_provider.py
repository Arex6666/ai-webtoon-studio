"""
Tongyi Wanxiang Image Provider - 通义万相图片生成
基于阿里云 DashScope API 实现，使用 Bearer Token 认证

支持:
- 文生图 (text-to-image) 使用 wan2.6-t2i 模型
"""
import httpx
import asyncio
import logging
import time
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TongyiImageRequest:
    """图片生成请求"""
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    n: int = 1  # 生成数量 1-4
    seed: Optional[int] = None


@dataclass
class TongyiImageResult:
    """图片生成结果"""
    success: bool
    image_url: Optional[str] = None
    task_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    generation_time: float = 0.0


class TongyiImageProvider:
    """
    通义万相图片生成 Provider
    
    使用 wan2.6-t2i 模型，支持同步调用
    API 文档: https://help.aliyun.com/zh/model-studio/developer-reference/text-to-image-v2
    """
    
    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY or settings.TONGYI_API_KEY
        self.base_url = "https://dashscope.aliyuncs.com/api/v1"
        self.model = "wanx2.1-t2i-turbo"  # 快速版本
        self.client = httpx.AsyncClient(timeout=180.0)
        
        if self.api_key:
            logger.info(f"[TongyiImage] Initialized with API key: {self.api_key[:10]}...")
    
    async def generate(
        self,
        request: TongyiImageRequest,
        progress_callback: Optional[callable] = None,
    ) -> TongyiImageResult:
        """
        生成图片 (异步任务模式)
        """
        if not self.api_key:
            return TongyiImageResult(
                success=False,
                error="DASHSCOPE_API_KEY 未配置",
                error_code="CONFIG_ERROR",
            )
        
        start_time = time.time()
        
        try:
            if progress_callback:
                progress_callback(0.1, "提交任务...")
            
            logger.info(f"[TongyiImage] Generating image with prompt: {request.prompt[:50]}...")
            
            # 1. 创建异步任务
            task_id = await self._create_task(request)
            if not task_id:
                return TongyiImageResult(
                    success=False,
                    error="Failed to create generation task",
                    error_code="TASK_CREATE_ERROR",
                )
            
            logger.info(f"[TongyiImage] Task created: {task_id}")
            
            if progress_callback:
                progress_callback(0.3, "等待生成...")
            
            # 2. 轮询任务状态
            image_url = await self._poll_task(task_id, progress_callback)
            
            if not image_url:
                return TongyiImageResult(
                    success=False,
                    task_id=task_id,
                    error="Generation failed or timed out",
                    error_code="GENERATION_ERROR",
                )
            
            generation_time = time.time() - start_time
            logger.info(f"[TongyiImage] Image generated in {generation_time:.2f}s: {image_url[:50]}...")
            
            return TongyiImageResult(
                success=True,
                image_url=image_url,
                task_id=task_id,
                generation_time=generation_time,
            )
            
        except Exception as e:
            logger.error(f"[TongyiImage] Generation failed: {e}")
            return TongyiImageResult(
                success=False,
                error=str(e),
                error_code="EXCEPTION",
                generation_time=time.time() - start_time,
            )
    
    async def _create_task(self, request: TongyiImageRequest) -> Optional[str]:
        """创建异步生成任务"""
        url = f"{self.base_url}/services/aigc/text2image/image-synthesis"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",  # 启用异步模式
        }
        
        # 构建请求体
        payload = {
            "model": self.model,
            "input": {
                "prompt": request.prompt,
            },
            "parameters": {
                "size": f"{request.width}*{request.height}",
                "n": request.n,
            }
        }
        
        if request.negative_prompt:
            payload["input"]["negative_prompt"] = request.negative_prompt
        
        if request.seed is not None:
            payload["parameters"]["seed"] = request.seed
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            data = response.json()
            
            logger.info(f"[TongyiImage] Create task response: {json.dumps(data, ensure_ascii=False)[:300]}")
            
            if response.status_code != 200:
                logger.error(f"[TongyiImage] Create task failed: {response.status_code} - {data}")
                return None
            
            # 获取任务 ID
            task_id = data.get("output", {}).get("task_id")
            return task_id
            
        except Exception as e:
            logger.error(f"[TongyiImage] Create task exception: {e}")
            return None
    
    async def _poll_task(
        self, 
        task_id: str, 
        progress_callback: Optional[callable] = None,
        max_attempts: int = 60,
        interval: float = 2.0
    ) -> Optional[str]:
        """轮询任务状态直到完成"""
        url = f"{self.base_url}/tasks/{task_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        for attempt in range(max_attempts):
            try:
                response = await self.client.get(url, headers=headers)
                data = response.json()
                
                output = data.get("output", {})
                status = output.get("task_status")
                
                if status == "SUCCEEDED":
                    # 获取图片 URL
                    results = output.get("results", [])
                    if results:
                        return results[0].get("url")
                    return None
                
                elif status == "FAILED":
                    error_msg = output.get("message", "Unknown error")
                    logger.error(f"[TongyiImage] Task failed: {error_msg}")
                    return None
                
                elif status in ["PENDING", "RUNNING"]:
                    if progress_callback:
                        progress = 0.3 + (attempt / max_attempts) * 0.6
                        progress_callback(progress, f"生成中 ({attempt + 1}/{max_attempts})...")
                    await asyncio.sleep(interval)
                
                else:
                    logger.warning(f"[TongyiImage] Unknown status: {status}")
                    await asyncio.sleep(interval)
                    
            except Exception as e:
                logger.error(f"[TongyiImage] Poll exception: {e}")
                await asyncio.sleep(interval)
        
        logger.error(f"[TongyiImage] Task timed out after {max_attempts} attempts")
        return None
    
    async def check_health(self) -> bool:
        """检查服务可用性"""
        return bool(self.api_key)


# 全局实例
_tongyi_image_provider: Optional[TongyiImageProvider] = None


def get_tongyi_image_provider() -> Optional[TongyiImageProvider]:
    """获取通义图片 Provider"""
    global _tongyi_image_provider
    if _tongyi_image_provider is None:
        api_key = settings.DASHSCOPE_API_KEY or settings.TONGYI_API_KEY
        if api_key:
            logger.info("[TongyiImage] Initializing provider...")
            _tongyi_image_provider = TongyiImageProvider()
    return _tongyi_image_provider
