"""
Tongyi Video Provider - 通义万相视频生成
基于阿里云 DashScope API 实现

支持模型:
- wanx2.1-i2v-plus: 图生视频 (推荐)
- wan2.1-t2v-plus: 文生视频
- wan2.2-kf2v-flash: 首尾帧生视频
"""
import httpx
import asyncio
import logging
import time
from typing import Optional, Dict, Any

from app.core.config import settings
from app.services.storage.media_persister import persist_media, MediaPersistError
from app.services.video.video_provider_base import (
    VideoProviderBase,
    VideoGenerationRequest,
    VideoJobStatus,
    VideoJobStatusInfo,
    VideoResult,
    register_provider,
)

logger = logging.getLogger(__name__)


class TongyiVideoProvider(VideoProviderBase):
    """
    通义万相视频生成 Provider
    
    使用 DashScope HTTP API 进行异步视频生成
    """
    
    provider_name = "tongyi"
    
    def __init__(self):
        self.api_key = settings.TONGYI_API_KEY
        self.base_url = "https://dashscope.aliyuncs.com/api/v1"
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # 默认模型配置
        self.model = "wanx2.1-i2v-plus"  # 图生视频
        self.t2v_model = "wan2.1-t2v-plus"  # 文生视频
        self.kf2v_model = "wan2.2-kf2v-flash"  # 首尾帧
    
    async def submit_job(self, request: VideoGenerationRequest) -> str:
        """
        提交视频生成任务到通义万相
        
        使用异步任务模式: 返回 task_id
        """
        if not self.api_key:
            raise ValueError("TONGYI_API_KEY not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",  # 启用异步模式
        }
        
        metadata = request.metadata if isinstance(request.metadata, dict) else {}

        # 根据输入类型选择模型
        if request.end_frame_url:
            # 首尾帧模式
            model = self.kf2v_model
            input_data = {
                "first_frame_url": request.start_frame_url,
                "last_frame_url": request.end_frame_url,
                "prompt": request.prompt,
            }
        elif request.start_frame_url:
            # 图生视频模式
            model = self.model
            input_data = {
                "image_url": request.start_frame_url,
                "prompt": request.prompt,
            }
        else:
            # 文生视频模式
            model = self.t2v_model
            input_data = {
                "prompt": request.prompt,
            }

        model_override = metadata.get("model")
        if isinstance(model_override, str) and model_override.strip():
            model = model_override.strip()

        prompt_extend = metadata.get("prompt_extend")
        if isinstance(prompt_extend, bool):
            prompt_extend_enabled = prompt_extend
        else:
            prompt_extend_enabled = True
        
        # 构建请求体
        payload = {
            "model": model,
            "input": input_data,
            "parameters": {
                "duration": int(request.duration_sec),
                "resolution": self._get_resolution(request.width, request.height),
                "prompt_extend": prompt_extend_enabled,  # 智能优化 prompt
            }
        }
        
        if request.seed:
            payload["parameters"]["seed"] = request.seed

        if request.negative_prompt:
            input_data["negative_prompt"] = request.negative_prompt

        logger.info(f"[TongyiVideo] Submitting job with model={model}")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/services/aigc/video-generation/generation",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "output" in data and "task_id" in data["output"]:
                task_id = data["output"]["task_id"]
                logger.info(f"[TongyiVideo] Job submitted: {task_id}")
                return task_id
            else:
                error = data.get("message", "Unknown error")
                raise Exception(f"Tongyi API error: {error}")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"[TongyiVideo] HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[TongyiVideo] Submit error: {e}")
            raise
    
    async def poll_status(self, job_id: str) -> VideoJobStatusInfo:
        """
        查询任务状态
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        try:
            response = await self.client.get(
                f"{self.base_url}/tasks/{job_id}",
                headers=headers,
            )
            response.raise_for_status()
            
            data = response.json()
            output = data.get("output", {})
            
            task_status = output.get("task_status", "PENDING")
            
            # 映射状态
            status_map = {
                "PENDING": VideoJobStatus.PENDING,
                "RUNNING": VideoJobStatus.PROCESSING,
                "SUCCEEDED": VideoJobStatus.COMPLETED,
                "FAILED": VideoJobStatus.FAILED,
            }
            
            status = status_map.get(task_status, VideoJobStatus.PENDING)
            
            # 计算进度
            progress = 0.0
            if task_status == "PENDING":
                progress = 0.1
            elif task_status == "RUNNING":
                # 从 task_metrics 获取进度
                metrics = output.get("task_metrics", {})
                total = metrics.get("TOTAL", 1)
                succeeded = metrics.get("SUCCEEDED", 0)
                progress = 0.2 + (succeeded / max(total, 1)) * 0.7
            elif task_status == "SUCCEEDED":
                progress = 1.0
            
            return VideoJobStatusInfo(
                job_id=job_id,
                external_job_id=job_id,
                status=status,
                progress=progress,
                message=output.get("message"),
                error=output.get("message") if task_status == "FAILED" else None,
            )
            
        except Exception as e:
            logger.error(f"[TongyiVideo] Poll error: {e}")
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
        }
        
        try:
            response = await self.client.get(
                f"{self.base_url}/tasks/{job_id}",
                headers=headers,
            )
            response.raise_for_status()
            
            data = response.json()
            output = data.get("output", {})
            
            if output.get("task_status") != "SUCCEEDED":
                return VideoResult(
                    success=False,
                    error=output.get("message", "Task not completed"),
                    provider=self.provider_name,
                )
            
            # 提取视频 URL
            video_url = output.get("video_url")

            # 提取预览帧（如果有）
            preview_url = None
            frames = []

            # 持久化到 MinIO
            try:
                if video_url:
                    video_url = await persist_media(video_url, "videos", "video/mp4")
            except MediaPersistError as e:
                logger.warning(f"[TongyiVideo] Failed to persist media: {e}")

            # 计算费用（根据分辨率和时长估算）
            usage = data.get("usage", {})
            cost = usage.get("video_count", 1) * 0.5

            return VideoResult(
                success=True,
                video_url=video_url,
                preview_url=preview_url,
                frames=frames,
                duration_sec=output.get("duration", 5),
                seed=output.get("seed"),
                provider=self.provider_name,
                cost=cost,
            )
            
        except Exception as e:
            logger.error(f"[TongyiVideo] Get result error: {e}")
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
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = await self.client.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=5.0,
            )
            return response.status_code == 200
        except:
            return False
    
    def _get_resolution(self, width: int, height: int) -> str:
        """转换分辨率格式"""
        # 通义万相支持的分辨率: 480P, 720P, 1080P
        if height >= 1080:
            return "1080P"
        elif height >= 720:
            return "720P"
        else:
            return "480P"


# 自动注册
def _register():
    if settings.TONGYI_API_KEY:
        provider = TongyiVideoProvider()
        register_provider("tongyi", provider)
        logger.info("[TongyiVideo] Provider registered")


# 模块加载时注册
_register()
