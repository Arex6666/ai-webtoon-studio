"""
S5-SC: Control Map Extractor

从锚点图提取各类控制图 (Depth, Lineart, Canny)。
"""
import logging
from typing import Optional, Dict
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ControlMapResult(BaseModel):
    """Control Map 提取结果"""
    success: bool
    maps: Dict[str, str] = {}  # {type: path}
    meta: dict = {}
    error: Optional[str] = None


SUPPORTED_MAP_TYPES = ["depth", "lineart", "canny"]


async def extract_control_maps(
    anchor_image_path: str,
    scene_id: str,
    map_types: list[str] = None,
    provider: str = "mock"
) -> ControlMapResult:
    """
    从锚点图提取控制图
    
    Args:
        anchor_image_path: 锚点图路径
        scene_id: 场景 ID
        map_types: 要提取的控制图类型 (默认全部)
        provider: 提取器 (mock/controlnet)
        
    Returns:
        ControlMapResult
    """
    if map_types is None:
        map_types = SUPPORTED_MAP_TYPES
    
    logger.info(f"[ControlMap] Extracting {map_types} for {scene_id}")
    
    if provider == "mock":
        return await _extract_mock(scene_id, map_types)
    elif provider == "controlnet":
        return await _extract_controlnet(anchor_image_path, scene_id, map_types)
    else:
        return ControlMapResult(success=False, error=f"Unknown provider: {provider}")


async def _extract_mock(scene_id: str, map_types: list[str]) -> ControlMapResult:
    """Mock 提取器"""
    import asyncio
    await asyncio.sleep(0.3)
    
    maps = {}
    for map_type in map_types:
        maps[map_type] = f"/storage/control_maps/{scene_id}/{map_type}.png"
    
    return ControlMapResult(
        success=True,
        maps=maps,
        meta={
            "provider": "mock",
            "types": map_types
        }
    )


async def _extract_controlnet(
    anchor_image_path: str,
    scene_id: str,
    map_types: list[str]
) -> ControlMapResult:
    """ControlNet 提取器"""
    # TODO: 实现真实的 ControlNet 调用
    # 使用 controlnet_aux 或 ComfyUI preprocessor 节点
    logger.warning("[ControlMap] ControlNet not implemented, falling back to mock")
    return await _extract_mock(scene_id, map_types)


async def extract_depth_map(image_path: str, scene_id: str) -> Optional[str]:
    """快捷方法: 仅提取深度图"""
    result = await extract_control_maps(image_path, scene_id, ["depth"])
    if result.success:
        return result.maps.get("depth")
    return None
