"""
Doubao Video Provider - 豆包视频生成
基于火山引擎 API 实现 (即梦 AI)

支持:
- 图生视频 (image-to-video)
"""
import httpx
import asyncio
import logging
import time
import json
from typing import Optional, Dict, Any

from app.core.config import settings
from app.services.video.video_provider_base import (
    VideoProviderBase,
    VideoGenerationRequest,
    VideoJobStatus,
    VideoJobStatusInfo,
    VideoResult,
    register_provider,
)

logger = logging.getLogger(__name__)


class DoubaoVideoProvider(VideoProviderBase):
    """
    豆包视频生成 Provider
    
    使用火山引擎/即梦 AI API 进行视频生成
    """
    
    provider_name = "doubao"
    
    def __init__(self):
        self.api_key = getattr(settings, 'DOUBAO_VIDEO_API_KEY', None) or settings.DOUBAO_API_KEY
        self.base_url = getattr(settings, 'DOUBAO_VIDEO_ENDPOINT', "https://open.volcengineapi.com")
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # API 版本
        self.api_version = "2024-05-01"
    
    async def submit_job(self, request: VideoGenerationRequest) -> str:
        """
        提交视频生成任务到豆包/即梦
        """
        if not self.api_key:
            raise ValueError("DOUBAO_VIDEO_API_KEY not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Api-Version": self.api_version,
        }
        
        # 构建请求体 - 图生视频
        payload = {
            "model": "jimeng-video-v1",  # 即梦视频模型
            "input": {
                "image_url": request.start_frame_url,
                "prompt": request.prompt,
            },
            "parameters": {
                "duration": int(request.duration_sec),
                "fps": request.fps,
                "resolution": f"{request.width}x{request.height}",
            }
        }
        
        if request.end_frame_url:
            payload["input"]["end_image_url"] = request.end_frame_url
        
        if request.seed:
            payload["parameters"]["seed"] = request.seed
        
        if request.negative_prompt:
            payload["input"]["negative_prompt"] = request.negative_prompt
        
        logger.info(f"[DoubaoVideo] Submitting job")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/video/generation",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "task_id" in data:
                task_id = data["task_id"]
                logger.info(f"[DoubaoVideo] Job submitted: {task_id}")
                return task_id
            elif "data" in data and "task_id" in data["data"]:
                task_id = data["data"]["task_id"]
                logger.info(f"[DoubaoVideo] Job submitted: {task_id}")
                return task_id
            else:
                error = data.get("message", data.get("error", "Unknown error"))
                raise Exception(f"Doubao API error: {error}")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"[DoubaoVideo] HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[DoubaoVideo] Submit error: {e}")
            raise
    
    async def poll_status(self, job_id: str) -> VideoJobStatusInfo:
        """
        查询任务状态
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Api-Version": self.api_version,
        }
        
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/video/task/{job_id}",
                headers=headers,
            )
            response.raise_for_status()
            
            data = response.json()
            task_data = data.get("data", data)
            
            task_status = task_data.get("status", "pending")
            
            # 映射状态
            status_map = {
                "pending": VideoJobStatus.PENDING,
                "processing": VideoJobStatus.PROCESSING,
                "running": VideoJobStatus.PROCESSING,
                "succeeded": VideoJobStatus.COMPLETED,
                "success": VideoJobStatus.COMPLETED,
                "failed": VideoJobStatus.FAILED,
                "error": VideoJobStatus.FAILED,
            }
            
            status = status_map.get(task_status.lower(), VideoJobStatus.PENDING)
            
            # 计算进度
            progress = task_data.get("progress", 0)
            if isinstance(progress, (int, float)):
                progress = progress / 100.0 if progress > 1 else progress
            else:
                progress = 0.5 if status == VideoJobStatus.PROCESSING else 0.0
            
            if status == VideoJobStatus.COMPLETED:
                progress = 1.0
            
            return VideoJobStatusInfo(
                job_id=job_id,
                external_job_id=job_id,
                status=status,
                progress=progress,
                message=task_data.get("message"),
                error=task_data.get("error_message") if status == VideoJobStatus.FAILED else None,
            )
            
        except Exception as e:
            logger.error(f"[DoubaoVideo] Poll error: {e}")
            return VideoJobStatusInfo(
                job_id=job_id,
                status=VideoJobStatus.FAILED,
                error=str(e),
            )
    
    async def get_result(self, job_id: str) -> VideoResult:
        """
        获取生成结果
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Api-Version": self.api_version,
        }
        
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/video/task/{job_id}",
                headers=headers,
            )
            response.raise_for_status()
            
            data = response.json()
            task_data = data.get("data", data)
            
            status = task_data.get("status", "").lower()
            if status not in ["succeeded", "success"]:
                return VideoResult(
                    success=False,
                    error=task_data.get("error_message", "Task not completed"),
                    provider=self.provider_name,
                )
            
            # 提取视频 URL
            output = task_data.get("output", {})
            video_url = output.get("video_url") or task_data.get("video_url")
            
            # 提取预览
            preview_url = output.get("cover_url") or output.get("preview_url")
            
            return VideoResult(
                success=True,
                video_url=video_url,
                preview_url=preview_url,
                frames=[],
                duration_sec=output.get("duration", 5),
                seed=output.get("seed"),
                provider=self.provider_name,
                cost=0.5,  # 估算费用
            )
            
        except Exception as e:
            logger.error(f"[DoubaoVideo] Get result error: {e}")
            return VideoResult(
                success=False,
                error=str(e),
                error_code="FETCH_FAILED",
                provider=self.provider_name,
            )
    
    async def check_health(self) -> bool:
        """检查服务可用性"""
        if not self.api_key:
            return False
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Api-Version": self.api_version,
            }
            response = await self.client.get(
                f"{self.base_url}/api/v1/health",
                headers=headers,
                timeout=5.0,
            )
            return response.status_code in [200, 404]  # 404 也表示服务在线
        except:
            return False


# 自动注册
def _register():
    api_key = getattr(settings, 'DOUBAO_VIDEO_API_KEY', None) or settings.DOUBAO_API_KEY
    if api_key:
        provider = DoubaoVideoProvider()
        register_provider("doubao", provider)
        logger.info("[DoubaoVideo] Provider registered")


# 模块加载时注册
_register()
