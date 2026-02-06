"""
S5-01 - Portrait Generator

调用图像生成服务（ComfyUI / Mock）生成角色参考肖像。
"""

import uuid
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

from .spec_generator import CharacterPortraitSpec
from .prompt_composer import compose_portrait_prompt, get_generation_params

logger = logging.getLogger(__name__)


class PortraitResult(BaseModel):
    """肖像生成结果"""
    success: bool
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    meta: dict = {}
    error: Optional[str] = None


async def generate_character_portrait(
    spec: CharacterPortraitSpec,
    provider: str = "mock",
    size: tuple[int, int] = (512, 512),
    seed: Optional[int] = None,
    output_dir: Optional[str] = None
) -> PortraitResult:
    """
    生成角色参考肖像
    
    Args:
        spec: 角色肖像规格
        provider: 生成服务 (mock, comfyui, sd_api)
        size: 图像尺寸
        seed: 随机种子
        output_dir: 输出目录
        
    Returns:
        PortraitResult
    """
    import random
    
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    
    params = get_generation_params(spec, size, seed)
    
    logger.info(f"[Portrait] Generating portrait for {spec.name} (provider={provider})")
    
    try:
        if provider == "mock":
            return await _generate_mock(spec, params, output_dir)
        elif provider == "comfyui":
            return await _generate_comfyui(spec, params, output_dir)
        else:
            return PortraitResult(
                success=False,
                error=f"Unknown provider: {provider}"
            )
    except Exception as e:
        logger.error(f"[Portrait] Generation failed: {e}")
        return PortraitResult(
            success=False,
            error=str(e)
        )


async def _generate_mock(
    spec: CharacterPortraitSpec,
    params: dict,
    output_dir: Optional[str]
) -> PortraitResult:
    """Mock 生成器（用于测试）"""
    import hashlib
    
    # 生成一个 placeholder 图片 URL
    prompt_hash = hashlib.md5(params["positive_prompt"].encode()).hexdigest()[:8]
    
    # 使用 placeholder 服务
    width = params["width"]
    height = params["height"]
    
    # 模拟保存路径
    filename = f"portrait_{spec.character_id}_{prompt_hash}.png"
    
    if output_dir:
        image_path = str(Path(output_dir) / filename)
    else:
        image_path = f"/portraits/{filename}"
    
    # 使用 placeholder 图片 URL
    image_url = f"https://via.placeholder.com/{width}x{height}/2a2a3a/ffffff?text={spec.name}"
    
    return PortraitResult(
        success=True,
        image_path=image_path,
        image_url=image_url,
        meta={
            "provider": "mock",
            "seed": params.get("seed"),
            "prompt_hash": prompt_hash,
            "style_profile": spec.style_profile,
            "generated_at": datetime.utcnow().isoformat()
        }
    )


async def _generate_comfyui(
    spec: CharacterPortraitSpec,
    params: dict,
    output_dir: Optional[str]
) -> PortraitResult:
    """ComfyUI 生成器"""
    import os
    import httpx
    import hashlib
    
    comfyui_url = os.getenv("COMFYUI_URL", "http://localhost:8188")
    
    # 构建 ComfyUI workflow
    workflow = _build_portrait_workflow(params)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 提交任务
        response = await client.post(
            f"{comfyui_url}/prompt",
            json={"prompt": workflow}
        )
        
        if response.status_code != 200:
            return PortraitResult(
                success=False,
                error=f"ComfyUI error: {response.text}"
            )
        
        result = response.json()
        prompt_id = result.get("prompt_id")
        
        if not prompt_id:
            return PortraitResult(
                success=False,
                error="No prompt_id returned"
            )
        
        # 等待完成并获取结果
        # TODO: 实现 polling 或 websocket
        import asyncio
        await asyncio.sleep(10)  # 临时等待
        
        # 获取输出
        history_response = await client.get(
            f"{comfyui_url}/history/{prompt_id}"
        )
        
        if history_response.status_code != 200:
            return PortraitResult(
                success=False,
                error="Failed to get history"
            )
        
        history = history_response.json()
        
        # 提取输出图片
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for img in node_output["images"]:
                        image_url = f"{comfyui_url}/view?filename={img['filename']}"
                        
                        prompt_hash = hashlib.md5(
                            params["positive_prompt"].encode()
                        ).hexdigest()[:8]
                        
                        return PortraitResult(
                            success=True,
                            image_url=image_url,
                            meta={
                                "provider": "comfyui",
                                "seed": params.get("seed"),
                                "prompt_hash": prompt_hash,
                                "style_profile": spec.style_profile,
                                "prompt_id": prompt_id,
                                "generated_at": datetime.utcnow().isoformat()
                            }
                        )
        
        return PortraitResult(
            success=False,
            error="No output images found"
        )


def _build_portrait_workflow(params: dict) -> dict:
    """构建 ComfyUI 肖像生成 workflow"""
    
    # 简化的 workflow（需要根据实际 ComfyUI 配置调整）
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": params.get("seed", 0),
                "steps": params.get("steps", 25),
                "cfg": params.get("cfg_scale", 7.0),
                "sampler_name": params.get("sampler", "euler_ancestral"),
                "scheduler": params.get("scheduler", "normal"),
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "sd_xl_base_1.0.safetensors"  # 配置化
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": params.get("width", 512),
                "height": params.get("height", 512),
                "batch_size": 1
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": params["positive_prompt"],
                "clip": ["4", 1]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": params["negative_prompt"],
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "portrait",
                "images": ["8", 0]
            }
        }
    }
