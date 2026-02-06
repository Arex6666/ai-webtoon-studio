"""
Video Provider Base - 视频生成 Provider 抽象基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class VideoJobStatus(str, Enum):
    """视频任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoGenerationRequest:
    """视频生成请求"""
    # 基础信息
    clip_id: str
    panel_id: str
    project_id: str
    chapter_id: str
    
    # 输入图片
    start_frame_url: str
    end_frame_url: Optional[str] = None  # 双关键帧模式
    
    # 生成参数
    prompt: str = ""
    negative_prompt: str = ""
    duration_sec: float = 3.0
    fps: int = 24
    
    # 输出参数
    width: int = 1080
    height: int = 1920
    
    # Provider 特定参数
    seed: Optional[int] = None
    motion_strength: float = 0.5  # 运动强度
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoJobStatusInfo:
    """视频任务状态信息"""
    job_id: str
    external_job_id: Optional[str] = None  # Provider 端的任务 ID
    status: VideoJobStatus = VideoJobStatus.PENDING
    progress: float = 0.0
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class VideoResult:
    """视频生成结果"""
    success: bool
    video_url: Optional[str] = None
    preview_url: Optional[str] = None
    frames: List[str] = field(default_factory=list)
    duration_sec: float = 0.0
    
    # 元数据
    seed: Optional[int] = None
    provider: str = ""
    cost: float = 0.0
    generation_time_ms: int = 0
    
    # 错误信息
    error: Optional[str] = None
    error_code: Optional[str] = None


class VideoProviderBase(ABC):
    """
    视频生成 Provider 抽象基类
    
    所有 Provider 实现必须继承此类并实现以下方法：
    - submit_job: 提交生成任务
    - poll_status: 查询任务状态
    - get_result: 获取生成结果
    """
    
    provider_name: str = "base"
    
    @abstractmethod
    async def submit_job(self, request: VideoGenerationRequest) -> str:
        """
        提交视频生成任务
        
        Args:
            request: 视频生成请求
            
        Returns:
            任务 ID (Provider 端)
        """
        pass
    
    @abstractmethod
    async def poll_status(self, job_id: str) -> VideoJobStatusInfo:
        """
        查询任务状态
        
        Args:
            job_id: 任务 ID (Provider 端)
            
        Returns:
            任务状态信息
        """
        pass
    
    @abstractmethod
    async def get_result(self, job_id: str) -> VideoResult:
        """
        获取生成结果
        
        Args:
            job_id: 任务 ID (Provider 端)
            
        Returns:
            视频生成结果
        """
        pass
    
    async def generate(
        self,
        request: VideoGenerationRequest,
        timeout: int = 300,
        poll_interval: float = 2.0,
        progress_callback: Optional[callable] = None,
    ) -> VideoResult:
        """
        便捷方法：一站式生成视频
        
        提交任务 → 轮询状态 → 获取结果
        
        Args:
            request: 视频生成请求
            timeout: 超时秒数
            poll_interval: 轮询间隔秒数
            progress_callback: 进度回调 callback(progress: float, message: str)
            
        Returns:
            视频生成结果
        """
        import asyncio
        import time
        
        start_time = time.time()
        
        # 1. 提交任务
        job_id = await self.submit_job(request)
        
        if progress_callback:
            progress_callback(0.1, "任务已提交")
        
        # 2. 轮询状态
        while time.time() - start_time < timeout:
            status = await self.poll_status(job_id)
            
            if progress_callback:
                progress_callback(status.progress, status.message or "生成中...")
            
            if status.status == VideoJobStatus.COMPLETED:
                break
            elif status.status == VideoJobStatus.FAILED:
                return VideoResult(
                    success=False,
                    error=status.error or "生成失败",
                    error_code="GENERATION_FAILED",
                    provider=self.provider_name,
                )
            
            await asyncio.sleep(poll_interval)
        else:
            return VideoResult(
                success=False,
                error=f"生成超时: {timeout}秒",
                error_code="TIMEOUT",
                provider=self.provider_name,
            )
        
        # 3. 获取结果
        result = await self.get_result(job_id)
        result.generation_time_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    @abstractmethod
    async def check_health(self) -> bool:
        """检查 Provider 可用性"""
        pass


# Provider 注册表
_providers: Dict[str, VideoProviderBase] = {}


def register_provider(name: str, provider: VideoProviderBase):
    """注册 Provider"""
    _providers[name] = provider


def get_video_provider(name: str) -> Optional[VideoProviderBase]:
    """获取 Provider"""
    return _providers.get(name)


def list_providers() -> List[str]:
    """列出所有已注册的 Provider"""
    return list(_providers.keys())
