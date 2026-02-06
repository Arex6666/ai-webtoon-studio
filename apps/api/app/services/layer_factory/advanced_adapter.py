"""
高级 ComfyUI 生成适配器
支持：角色一致性、ControlNet、Inpaint、图层分离
"""
import asyncio
import io
import uuid
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from app.core.config import settings
from app.services.layer_factory.comfyui_client import get_comfyui_client, BaseComfyUIClient
from app.services.layer_factory.workflow_builder import get_workflow_builder

logger = logging.getLogger(__name__)


class GenerationType(str, Enum):
    """生成类型"""
    BASIC = "basic"                    # 基础文生图
    IPADAPTER = "ipadapter"            # IP-Adapter 角色一致性
    CONTROLNET = "controlnet"          # ControlNet 控制
    INPAINT = "inpaint"                # 局部重绘
    LAYER_SEPARATION = "layer_sep"     # 图层分离
    DEPTH = "depth"                    # 深度图估计
    POSE = "pose"                      # 姿态估计


class AdvancedComfyUIAdapter:
    """
    高级 ComfyUI 适配器
    
    统一接口支持多种生成类型
    """
    
    def __init__(self):
        self.client: BaseComfyUIClient = get_comfyui_client()
        self.builder = get_workflow_builder()
    
    # ============ 基础文生图 ============
    
    async def generate_basic(
        self,
        positive_prompt: str,
        negative_prompt: str = "",
        width: int = 1080,
        height: int = 1920,
        seed: int = None,
        steps: int = 20,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """基础 Flux 文生图"""
        if seed is None:
            seed = int(time.time() * 1000) % 2147483647
        
        workflow = self.builder.build_workflow("flux_basic", {
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    # ============ IP-Adapter 角色一致性 ============
    
    async def generate_with_reference(
        self,
        positive_prompt: str,
        reference_image_url: str,
        ipadapter_weight: float = 0.8,
        width: int = 1080,
        height: int = 1920,
        seed: int = None,
        steps: int = 20,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        使用参考图生成（角色一致性）
        
        Args:
            reference_image_url: 参考人物图片 URL
            ipadapter_weight: IP-Adapter 权重 (0-1)
        """
        if seed is None:
            seed = int(time.time() * 1000) % 2147483647
        
        workflow = self.builder.build_workflow("flux_ipadapter", {
            "positive_prompt": positive_prompt,
            "reference_image": reference_image_url,
            "ipadapter_weight": ipadapter_weight,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    # ============ ControlNet 控制生成 ============
    
    async def generate_with_control(
        self,
        positive_prompt: str,
        control_image_url: str,
        control_type: str = "depth",  # depth, pose, canny, lineart
        control_strength: float = 0.8,
        negative_prompt: str = "",
        width: int = 1080,
        height: int = 1920,
        seed: int = None,
        steps: int = 20,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        使用控制图生成 (ControlNet)
        
        Args:
            control_image_url: 控制图 URL (深度图/姿态图/边缘图)
            control_type: 控制类型
            control_strength: 控制强度 (0-1)
        """
        if seed is None:
            seed = int(time.time() * 1000) % 2147483647
        
        # 根据类型选择 ControlNet 模型
        controlnet_models = {
            "depth": "control_v11f1p_sd15_depth_fp16.safetensors",
            "pose": "control_v11p_sd15_openpose_fp16.safetensors",
            "canny": "control_v11p_sd15_canny_fp16.safetensors",
            "lineart": "control_v11p_sd15_lineart_fp16.safetensors",
            "scribble": "control_v11p_sd15_scribble_fp16.safetensors",
        }
        
        workflow = self.builder.build_workflow("flux_controlnet", {
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "control_image": control_image_url,
            "controlnet_model": controlnet_models.get(control_type, controlnet_models["depth"]),
            "controlnet_strength": control_strength,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    # ============ 局部重绘 ============
    
    async def inpaint(
        self,
        source_image_url: str,
        mask_image_url: str,
        positive_prompt: str,
        denoise: float = 0.8,
        grow_mask: int = 8,
        seed: int = None,
        steps: int = 20,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        局部重绘
        
        Args:
            source_image_url: 原图 URL
            mask_image_url: 遮罩图 URL (白色区域将被重绘)
            denoise: 去噪强度 (0-1，越高变化越大)
            grow_mask: 遮罩扩展像素
        """
        if seed is None:
            seed = int(time.time() * 1000) % 2147483647
        
        workflow = self.builder.build_workflow("flux_inpaint", {
            "source_image": source_image_url,
            "mask_image": mask_image_url,
            "positive_prompt": positive_prompt,
            "denoise": denoise,
            "grow_mask": grow_mask,
            "seed": seed,
            "steps": steps,
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    # ============ 图层分离 ============
    
    async def separate_layers(
        self,
        source_image_url: str,
        point_coords: List[List[int]] = None,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        图层分离 - 分离角色和背景
        
        Args:
            source_image_url: 原图 URL
            point_coords: SAM 点击坐标 [[x, y], ...]
        
        Returns:
            {"mask_url": ..., "char_url": ..., "bg_url": ...}
        """
        if point_coords is None:
            # 默认点击图片中心
            point_coords = [[540, 960]]
        
        workflow = self.builder.build_workflow("layer_separation", {
            "source_image": source_image_url,
            "point_coords": str(point_coords),
            "point_labels": str([1] * len(point_coords)),
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    # ============ 控制图估计 ============
    
    async def estimate_depth(
        self,
        source_image_url: str,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """估计深度图"""
        workflow = self.builder.build_workflow("depth_estimation", {
            "source_image": source_image_url,
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    async def estimate_pose(
        self,
        source_image_url: str,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """估计姿态图"""
        workflow = self.builder.build_workflow("pose_estimation", {
            "source_image": source_image_url,
        })
        
        return await self._execute_workflow(workflow, progress_callback)
    
    # ============ 内部方法 ============
    
    async def _execute_workflow(
        self,
        workflow: Dict[str, Any],
        progress_callback: callable = None,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """执行 workflow 并等待结果"""
        # 提交任务
        prompt_id = await self.client.submit_workflow(workflow)
        logger.info(f"Submitted workflow: {prompt_id}")
        
        # 等待完成
        start_time = time.time()
        last_progress = 0
        
        while time.time() - start_time < timeout:
            status = await self.client.poll_status(prompt_id)
            current_status = status.get("status", "pending")
            progress = status.get("progress", 0)
            
            if progress != last_progress and progress_callback:
                progress_callback(progress / 100.0)
                last_progress = progress
            
            if current_status == "completed":
                # 获取输出
                outputs = await self.client.fetch_outputs(prompt_id)
                return {
                    "prompt_id": prompt_id,
                    "status": "completed",
                    "outputs": outputs,
                    "duration_ms": int((time.time() - start_time) * 1000),
                }
            
            elif current_status == "failed":
                error = status.get("error", "Unknown error")
                raise Exception(f"Workflow failed: {error}")
            
            await asyncio.sleep(1.0)
        
        raise TimeoutError(f"Workflow {prompt_id} timed out after {timeout}s")


# 全局实例
_advanced_adapter: Optional[AdvancedComfyUIAdapter] = None


def get_advanced_adapter() -> AdvancedComfyUIAdapter:
    """获取高级适配器单例"""
    global _advanced_adapter
    if _advanced_adapter is None:
        _advanced_adapter = AdvancedComfyUIAdapter()
    return _advanced_adapter
