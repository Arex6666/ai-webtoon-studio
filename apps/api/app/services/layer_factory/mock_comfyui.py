"""
Mock ComfyUI Client - 开发测试用
生成假的图层数据
"""
import asyncio
import uuid
import io
import logging
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont
import random

from .comfyui_client import BaseComfyUIClient

logger = logging.getLogger(__name__)


class MockComfyUIClient(BaseComfyUIClient):
    """
    Mock ComfyUI 客户端
    用于开发和测试，生成占位图片
    """
    
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
    
    async def submit_workflow(self, workflow: Dict[str, Any]) -> str:
        """模拟提交工作流"""
        job_id = f"mock_{uuid.uuid4().hex[:8]}"
        
        self._jobs[job_id] = {
            "status": "pending",
            "progress": 0,
            "workflow": workflow,
            "created_at": asyncio.get_event_loop().time()
        }
        
        # 启动异步处理
        asyncio.create_task(self._process_job(job_id))
        
        logger.info(f"Mock ComfyUI: Job submitted - {job_id}")
        return job_id
    
    async def _process_job(self, job_id: str):
        """模拟处理任务"""
        if job_id not in self._jobs:
            return
        
        job = self._jobs[job_id]
        
        # 模拟处理时间
        for i in range(10):
            await asyncio.sleep(0.3)  # 总共约3秒
            job["progress"] = (i + 1) * 10
            job["status"] = "processing"
        
        # 生成 Mock 图层
        try:
            job["outputs"] = await self._generate_mock_layers()
            job["status"] = "completed"
            job["progress"] = 100
            logger.info(f"Mock ComfyUI: Job completed - {job_id}")
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
            logger.error(f"Mock ComfyUI: Job failed - {job_id}: {e}")
    
    async def _generate_mock_layers(self) -> Dict[str, List[bytes]]:
        """生成 Mock 图层图片"""
        width, height = 1024, 1024
        outputs = {}
        
        # 生成背景层（带渐变的背景）
        bg_img = self._create_mock_background(width, height)
        outputs["bg"] = [self._image_to_bytes(bg_img)]
        
        # 生成人物层（带透明背景的简单形状）
        char_img = self._create_mock_character(width, height)
        outputs["char"] = [self._image_to_bytes(char_img)]
        
        # 生成完整预览
        full_img = Image.new("RGBA", (width, height))
        full_img.paste(bg_img.convert("RGBA"), (0, 0))
        full_img.paste(char_img, (0, 0), char_img)
        outputs["full"] = [self._image_to_bytes(full_img)]
        
        # 生成蒙版
        mask_img = self._create_mock_mask(width, height)
        outputs["mask"] = [self._image_to_bytes(mask_img)]
        
        return outputs
    
    def _create_mock_background(self, width: int, height: int) -> Image.Image:
        """创建 Mock 背景"""
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        
        # 渐变背景
        for y in range(height):
            r = int(135 + (y / height) * 50)
            g = int(206 + (y / height) * 30)
            b = int(235 - (y / height) * 50)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # 添加一些装饰
        for _ in range(5):
            x = random.randint(0, width)
            y = random.randint(0, height // 2)
            r = random.randint(20, 50)
            draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, 100))
        
        # 添加文字标记
        draw.text((10, 10), "MOCK BG", fill=(100, 100, 100))
        
        return img
    
    def _create_mock_character(self, width: int, height: int) -> Image.Image:
        """创建 Mock 人物层（透明背景）"""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 简单的人物轮廓
        center_x = width // 2
        base_y = height - 100
        
        # 身体
        body_color = (100, 149, 237, 255)  # 天蓝色
        draw.ellipse([
            center_x - 80, base_y - 300,
            center_x + 80, base_y - 100
        ], fill=body_color)
        
        # 头
        head_color = (255, 218, 185, 255)  # 肤色
        draw.ellipse([
            center_x - 60, base_y - 450,
            center_x + 60, base_y - 300
        ], fill=head_color)
        
        # 眼睛
        eye_color = (50, 50, 50, 255)
        draw.ellipse([center_x - 30, base_y - 400, center_x - 10, base_y - 380], fill=eye_color)
        draw.ellipse([center_x + 10, base_y - 400, center_x + 30, base_y - 380], fill=eye_color)
        
        # 添加标记
        draw.text((10, 10), "MOCK CHAR", fill=(100, 100, 100, 255))
        
        return img
    
    def _create_mock_mask(self, width: int, height: int) -> Image.Image:
        """创建 Mock 蒙版"""
        img = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(img)
        
        # 人物区域蒙版
        center_x = width // 2
        base_y = height - 100
        
        draw.ellipse([
            center_x - 80, base_y - 300,
            center_x + 80, base_y - 100
        ], fill=255)
        
        draw.ellipse([
            center_x - 60, base_y - 450,
            center_x + 60, base_y - 300
        ], fill=255)
        
        return img
    
    def _image_to_bytes(self, img: Image.Image) -> bytes:
        """将 Image 转换为 bytes"""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    
    async def poll_status(self, job_id: str) -> Dict[str, Any]:
        """查询任务状态"""
        if job_id not in self._jobs:
            return {"status": "not_found"}
        
        job = self._jobs[job_id]
        return {
            "status": job["status"],
            "progress": job["progress"],
            "error": job.get("error")
        }
    
    async def fetch_outputs(self, job_id: str) -> List[bytes]:
        """获取输出"""
        if job_id not in self._jobs:
            return []
        
        job = self._jobs[job_id]
        if job["status"] != "completed":
            return []
        
        outputs = job.get("outputs", {})
        # 返回所有图层的第一张图片
        result = []
        for layer_type in ["full", "char", "bg", "mask"]:
            if layer_type in outputs and outputs[layer_type]:
                result.append(outputs[layer_type][0])
        
        return result
    
    async def fetch_layer_outputs(self, job_id: str) -> Dict[str, bytes]:
        """获取分层输出"""
        if job_id not in self._jobs:
            return {}
        
        job = self._jobs[job_id]
        if job["status"] != "completed":
            return {}
        
        outputs = job.get("outputs", {})
        result = {}
        for layer_type, images in outputs.items():
            if images:
                result[layer_type] = images[0]
        
        return result
    
    async def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "cancelled"
            return True
        return False
    
    async def check_health(self) -> bool:
        """始终返回健康"""
        return True
