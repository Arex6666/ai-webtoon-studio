"""
ComfyUI Client - 与 ComfyUI 服务通信
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseComfyUIClient(ABC):
    """ComfyUI 客户端基类"""
    
    @abstractmethod
    async def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        """提交工作流，返回任务 ID"""
        pass
    
    @abstractmethod
    async def poll_status(self, job_id: str) -> Dict[str, Any]:
        """查询任务状态"""
        pass
    
    @abstractmethod
    async def fetch_outputs(self, job_id: str) -> List[bytes]:
        """获取输出文件"""
        pass
    
    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        pass


class ComfyUIClient(BaseComfyUIClient):
    """
    真实 ComfyUI 客户端
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=300.0)
    
    async def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        """提交工作流到 ComfyUI"""
        try:
            response = await self.client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("prompt_id", "")
        except Exception as e:
            logger.error(f"Failed to submit workflow: {e}")
            raise
    
    async def poll_status(self, job_id: str) -> Dict[str, Any]:
        """查询任务状态"""
        try:
            response = await self.client.get(
                f"{self.base_url}/history/{job_id}"
            )
            response.raise_for_status()
            data = response.json()
            
            if job_id in data:
                job_data = data[job_id]
                status = job_data.get("status", {})
                
                if status.get("status_str") == "success":
                    return {
                        "status": "completed",
                        "progress": 100,
                        "outputs": job_data.get("outputs", {})
                    }
                elif status.get("status_str") == "error":
                    return {
                        "status": "failed",
                        "error": status.get("exception_message", "Unknown error")
                    }
                else:
                    return {
                        "status": "processing",
                        "progress": 50
                    }
            
            return {"status": "pending", "progress": 0}
            
        except Exception as e:
            logger.error(f"Failed to poll status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def fetch_outputs(self, job_id: str) -> List[bytes]:
        """获取输出图片"""
        outputs = []
        try:
            status = await self.poll_status(job_id)
            if status.get("status") != "completed":
                return outputs
            
            output_data = status.get("outputs", {})
            for node_id, node_outputs in output_data.items():
                images = node_outputs.get("images", [])
                for img in images:
                    filename = img.get("filename")
                    subfolder = img.get("subfolder", "")
                    
                    response = await self.client.get(
                        f"{self.base_url}/view",
                        params={
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": "output"
                        }
                    )
                    if response.status_code == 200:
                        outputs.append(response.content)
            
            return outputs
            
        except Exception as e:
            logger.error(f"Failed to fetch outputs: {e}")
            return outputs
    
    async def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        try:
            response = await self.client.post(
                f"{self.base_url}/interrupt"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False
    
    async def check_health(self) -> bool:
        """检查 ComfyUI 服务健康状态"""
        try:
            response = await self.client.get(f"{self.base_url}/system_stats")
            return response.status_code == 200
        except:
            return False


def get_comfyui_client() -> BaseComfyUIClient:
    """
    获取 ComfyUI 客户端
    如果配置了 COMFYUI_URL 则使用真实客户端，否则使用 Mock
    """
    if settings.COMFYUI_URL:
        return ComfyUIClient(settings.COMFYUI_URL)
    else:
        from .mock_comfyui import MockComfyUIClient
        return MockComfyUIClient()
