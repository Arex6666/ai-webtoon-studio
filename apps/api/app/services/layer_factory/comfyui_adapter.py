"""
ComfyUI 生成适配器
统一封装 ComfyUI 调用流程
"""
import asyncio
import io
import uuid
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from app.core.config import settings
from app.services.layer_factory.comfyui_client import get_comfyui_client, BaseComfyUIClient
from app.services.layer_factory.workflow_builder import build_flux_workflow
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


class ComfyUIAdapter:
    """
    ComfyUI 生成适配器
    
    提供统一的接口：
    - submit(): 提交生成任务
    - poll(): 查询进度
    - complete(): 获取结果并上传到存储
    - generate(): 一站式生成并返回 URL
    """
    
    def __init__(self):
        self.client: BaseComfyUIClient = get_comfyui_client()
        self.storage = get_object_store()
    
    async def submit(
        self,
        positive_prompt: str,
        negative_prompt: str = "",
        width: int = 1080,
        height: int = 1920,
        seed: int = None,
        steps: int = 20,
        sampler: str = "euler",
        scheduler: str = "normal",
    ) -> str:
        """
        提交生成任务
        
        Returns:
            ComfyUI prompt_id
        """
        if seed is None:
            seed = int(time.time() * 1000) % 2147483647
        
        workflow = build_flux_workflow(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            sampler=sampler,
            scheduler=scheduler,
        )
        
        prompt_id = await self.client.submit_workflow(workflow)
        logger.info(f"Submitted ComfyUI job: {prompt_id}")
        return prompt_id
    
    async def poll(self, prompt_id: str) -> Dict[str, Any]:
        """
        查询任务状态
        
        Returns:
            {"status": "pending|processing|completed|failed", "progress": 0-100, ...}
        """
        return await self.client.poll_status(prompt_id)
    
    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout: int = 300,
        poll_interval: float = 1.0,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            prompt_id: ComfyUI prompt ID
            timeout: 超时秒数
            poll_interval: 轮询间隔
            progress_callback: 进度回调 callback(progress: float)
        
        Returns:
            最终状态
        """
        start_time = time.time()
        last_progress = 0
        
        while time.time() - start_time < timeout:
            status = await self.poll(prompt_id)
            
            current_status = status.get("status", "pending")
            progress = status.get("progress", 0)
            
            if progress != last_progress and progress_callback:
                progress_callback(progress / 100.0)
                last_progress = progress
            
            if current_status == "completed":
                return status
            elif current_status == "failed":
                error = status.get("error", "Unknown error")
                raise Exception(f"ComfyUI job failed: {error}")
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"ComfyUI job {prompt_id} timed out after {timeout}s")
    
    async def fetch_and_upload(
        self,
        prompt_id: str,
        project_id: str,
        chapter_id: str,
        panel_id: str,
        attempt: int = 1,
    ) -> Dict[str, str]:
        """
        获取生成结果并上传到存储
        
        Returns:
            {"full_url": "...", "manifest_url": "..."}
        """
        # 获取输出图片
        outputs = await self.client.fetch_outputs(prompt_id)
        
        if not outputs:
            raise Exception("No outputs from ComfyUI")
        
        # 上传第一张图片作为 full
        full_image = outputs[0]
        attempt_id = f"attempt-{attempt:03d}"
        layerpack_id = f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
        # 构建存储路径
        storage_prefix = f"{project_id}/{chapter_id}/{panel_id}/{attempt_id}"
        full_key = f"{storage_prefix}/full.png"
        
        # 上传图片
        full_url = await self.storage.upload_file(
            file_content=full_image,
            key=full_key,
            content_type="image/png"
        )
        
        # 创建并上传 manifest
        manifest = {
            "version": "1.0.0",
            "id": layerpack_id,
            "panel_id": panel_id,
            "project_id": project_id,
            "chapter_id": chapter_id,
            "attempt": attempt,
            "dimensions": {
                "width": 1080,
                "height": 1920,
                "aspect": "9:16"
            },
            "outputs": {
                "full": "full.png"
            },
            "metadata": {
                "created_at": datetime.utcnow().isoformat() + "Z",
                "comfyui_prompt_id": prompt_id,
            }
        }
        
        manifest_key = f"{storage_prefix}/manifest.json"
        import json
        manifest_url = await self.storage.upload_file(
            file_content=json.dumps(manifest, indent=2).encode("utf-8"),
            key=manifest_key,
            content_type="application/json"
        )
        
        return {
            "layerpack_id": layerpack_id,
            "full_url": full_url,
            "manifest_url": manifest_url,
        }
    
    async def generate(
        self,
        positive_prompt: str,
        project_id: str,
        chapter_id: str,
        panel_id: str,
        attempt: int = 1,
        negative_prompt: str = "",
        width: int = 1080,
        height: int = 1920,
        seed: int = None,
        steps: int = 20,
        progress_callback: callable = None,
    ) -> Dict[str, str]:
        """
        一站式生成：提交 → 等待 → 上传
        
        Returns:
            {"layerpack_id": "...", "full_url": "...", "manifest_url": "..."}
        """
        # 1. 提交任务
        prompt_id = await self.submit(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
        )
        
        # 2. 等待完成
        await self.wait_for_completion(
            prompt_id=prompt_id,
            progress_callback=progress_callback,
        )
        
        # 3. 获取并上传
        result = await self.fetch_and_upload(
            prompt_id=prompt_id,
            project_id=project_id,
            chapter_id=chapter_id,
            panel_id=panel_id,
            attempt=attempt,
        )
        
        return result


# 全局实例
_adapter: Optional[ComfyUIAdapter] = None


def get_comfyui_adapter() -> ComfyUIAdapter:
    """获取 ComfyUI Adapter 单例"""
    global _adapter
    if _adapter is None:
        _adapter = ComfyUIAdapter()
    return _adapter
