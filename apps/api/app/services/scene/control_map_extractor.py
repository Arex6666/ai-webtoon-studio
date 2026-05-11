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
    elif provider == "cv2":
        return await _extract_cv2(anchor_image_path, scene_id, map_types)
    elif provider == "controlnet":
        # ControlNet preprocessor stack (depth/lineart via controlnet_aux) is deferred.
        # Fall through to cv2 for canny-only support.
        logger.warning("[ControlMap] ControlNet not implemented, falling back to cv2 (canny only)")
        return await _extract_cv2(anchor_image_path, scene_id, map_types)
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


async def _extract_cv2(
    anchor_image_path: str,
    scene_id: str,
    map_types: list[str],
) -> ControlMapResult:
    """Extract control maps via OpenCV. Currently supports only canny.

    depth + lineart are explicitly skipped — they require ML preprocessor models
    (controlnet_aux + torch + GPU) which are deferred until ComfyUI rendering
    is enabled.
    """
    import cv2
    import numpy as np
    from app.services.scene_anchor.anchor_storage import get_anchor_storage

    storage = get_anchor_storage()
    anchor_bytes = await storage.load_anchor_image(scene_id)
    if not anchor_bytes:
        return ControlMapResult(
            success=False,
            error=f"anchor image not found for {scene_id}",
        )

    img_array = np.frombuffer(anchor_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ControlMapResult(
            success=False,
            error="failed to decode anchor image",
        )

    result_maps: dict[str, str] = {}
    skipped: list[str] = []

    for map_type in map_types:
        if map_type == "canny":
            canny = cv2.Canny(img, 100, 200)
            ok, encoded = cv2.imencode(".png", canny)
            if not ok:
                logger.error("[ControlMap] cv2.imencode failed for canny")
                continue
            canny_bytes = encoded.tobytes()
            canny_path = await storage.save_control_map(
                scene_id, "canny", canny_bytes
            )
            result_maps["canny"] = canny_path
        elif map_type in ("depth", "lineart"):
            skipped.append(map_type)
            logger.info(
                f"[ControlMap] {map_type} skipped — needs ML preprocessor (deferred)"
            )
        else:
            skipped.append(map_type)
            logger.warning(f"[ControlMap] unknown map_type: {map_type}")

    return ControlMapResult(
        success=True,
        maps=result_maps,
        meta={"provider": "cv2", "skipped": skipped, "thresholds": [100, 200]},
    )


async def extract_depth_map(image_path: str, scene_id: str) -> Optional[str]:
    """快捷方法: 仅提取深度图"""
    result = await extract_control_maps(image_path, scene_id, ["depth"])
    if result.success:
        return result.maps.get("depth")
    return None
