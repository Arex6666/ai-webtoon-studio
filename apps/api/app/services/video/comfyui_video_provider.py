"""
ComfyUI Video Provider - 基于 ComfyUI 的视频生成
使用 AnimateDiff 或其他视频生成工作流
"""
import asyncio
import logging
import time
import uuid
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
from app.services.layer_factory.comfyui_client import get_comfyui_client
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


class ComfyUIVideoProvider(VideoProviderBase):
    """
    ComfyUI 视频生成 Provider
    
    使用 AnimateDiff 工作流进行视频生成
    """
    
    provider_name = "comfyui"
    
    def __init__(self):
        self.client = get_comfyui_client()
        self.storage = get_object_store()
        self._jobs: Dict[str, Dict[str, Any]] = {}  # 本地任务跟踪
    
    async def submit_job(self, request: VideoGenerationRequest) -> str:
        """
        提交视频生成任务到 ComfyUI
        """
        if not settings.COMFYUI_URL:
            raise ValueError("COMFYUI_URL not configured")
        
        # 构建 AnimateDiff 工作流
        workflow = self._build_animatediff_workflow(request)
        
        # 提交到 ComfyUI
        prompt_id = await self.client.submit_workflow(workflow)
        
        # 本地跟踪
        job_id = f"comfy-video-{prompt_id}"
        self._jobs[job_id] = {
            "prompt_id": prompt_id,
            "request": request,
            "status": VideoJobStatus.PENDING,
            "created_at": time.time(),
        }
        
        logger.info(f"[ComfyUIVideo] Job submitted: {job_id}")
        return job_id
    
    async def poll_status(self, job_id: str) -> VideoJobStatusInfo:
        """
        查询任务状态
        """
        job_data = self._jobs.get(job_id)
        if not job_data:
            return VideoJobStatusInfo(
                job_id=job_id,
                status=VideoJobStatus.FAILED,
                error="Job not found",
            )
        
        prompt_id = job_data["prompt_id"]
        
        try:
            status = await self.client.poll_status(prompt_id)
            
            comfy_status = status.get("status", "pending")
            
            if comfy_status == "completed":
                job_data["status"] = VideoJobStatus.COMPLETED
                return VideoJobStatusInfo(
                    job_id=job_id,
                    external_job_id=prompt_id,
                    status=VideoJobStatus.COMPLETED,
                    progress=1.0,
                )
            elif comfy_status == "failed":
                job_data["status"] = VideoJobStatus.FAILED
                return VideoJobStatusInfo(
                    job_id=job_id,
                    external_job_id=prompt_id,
                    status=VideoJobStatus.FAILED,
                    error=status.get("error", "Generation failed"),
                )
            else:
                progress = status.get("progress", 50) / 100.0
                return VideoJobStatusInfo(
                    job_id=job_id,
                    external_job_id=prompt_id,
                    status=VideoJobStatus.PROCESSING,
                    progress=progress,
                )
                
        except Exception as e:
            logger.error(f"[ComfyUIVideo] Poll error: {e}")
            return VideoJobStatusInfo(
                job_id=job_id,
                status=VideoJobStatus.FAILED,
                error=str(e),
            )
    
    async def get_result(self, job_id: str) -> VideoResult:
        """
        获取生成结果
        """
        job_data = self._jobs.get(job_id)
        if not job_data:
            return VideoResult(
                success=False,
                error="Job not found",
                provider=self.provider_name,
            )
        
        prompt_id = job_data["prompt_id"]
        request = job_data["request"]
        
        try:
            # 获取输出
            outputs = await self.client.fetch_outputs(prompt_id)
            
            if not outputs:
                return VideoResult(
                    success=False,
                    error="No outputs from ComfyUI",
                    provider=self.provider_name,
                )
            
            # 上传到存储
            video_data = outputs[0]
            storage_key = f"{request.project_id}/{request.chapter_id}/videos/{request.clip_id}.mp4"
            
            video_url = await self.storage.upload_file(
                file_content=video_data,
                key=storage_key,
                content_type="video/mp4",
            )
            
            return VideoResult(
                success=True,
                video_url=video_url,
                duration_sec=request.duration_sec,
                provider=self.provider_name,
            )
            
        except Exception as e:
            logger.error(f"[ComfyUIVideo] Get result error: {e}")
            return VideoResult(
                success=False,
                error=str(e),
                error_code="FETCH_FAILED",
                provider=self.provider_name,
            )
    
    async def check_health(self) -> bool:
        """检查 ComfyUI 服务可用性"""
        if not settings.COMFYUI_URL:
            return False
        
        try:
            if hasattr(self.client, 'check_health'):
                return await self.client.check_health()
            return True
        except:
            return False
    
    def _build_animatediff_workflow(self, request: VideoGenerationRequest) -> Dict[str, Any]:
        """
        构建 AnimateDiff 视频生成工作流
        
        这是一个简化版本，实际应根据 ComfyUI 配置的工作流调整
        """
        seed = request.seed or int(time.time() * 1000) % 2147483647
        
        # 基础 AnimateDiff 工作流
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.ckpt"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": request.width,
                    "height": request.height,
                    "batch_size": int(request.duration_sec * request.fps),
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": request.prompt,
                    "clip": ["4", 1],
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": request.negative_prompt or "low quality, blurry",
                    "clip": ["4", 1],
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2],
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"video_{request.clip_id}",
                    "images": ["8", 0],
                }
            }
        }
        
        return workflow


# 自动注册
def _register():
    if settings.COMFYUI_URL:
        provider = ComfyUIVideoProvider()
        register_provider("comfyui", provider)
        logger.info("[ComfyUIVideo] Provider registered")


# 模块加载时注册
_register()
