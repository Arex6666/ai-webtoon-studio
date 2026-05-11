"""
S5-SC: Scene Anchor Retry Strategy

场景锚点生成的重试与编排逻辑。
"""
import logging
from typing import Optional, Tuple

from .anchor_generator import SceneAnchorSpec, generate_scene_anchor, AnchorResult
from .control_map_extractor import extract_control_maps, ControlMapResult

logger = logging.getLogger(__name__)


MAX_ATTEMPTS = 3


async def generate_anchor_with_retry(
    spec: SceneAnchorSpec,
    provider: str = "mock",
    size: tuple[int, int] = (768, 512)
) -> Tuple[bool, Optional[str], dict]:
    """
    带重试的场景锚点生成
    
    Returns:
        (success, anchor_path, meta)
    """
    meta = {
        "attempts": 0,
        "final_status": "pending",
        "error": None
    }
    
    for attempt in range(MAX_ATTEMPTS):
        meta["attempts"] = attempt + 1
        logger.info(f"[SceneAnchor] Attempt {attempt + 1}/{MAX_ATTEMPTS} for {spec.name}")
        
        result = await generate_scene_anchor(
            spec=spec,
            provider=provider,
            size=size
        )
        
        if result.success:
            meta["final_status"] = "ready"
            return True, result.image_path or result.image_url, {**meta, **result.meta}
        else:
            logger.warning(f"[SceneAnchor] Attempt {attempt + 1} failed: {result.error}")
            meta["error"] = result.error
    
    meta["final_status"] = "failed"
    return False, None, meta


async def enqueue_scene_anchor_generation(
    scene_id: str,
    project_id: str,
    scene_name: str,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    mood: Optional[str] = None,
    anchor_provider: str = "doubao",
    control_map_provider: str = "cv2",
    db_session = None,
) -> dict:
    """
    入队场景锚点生成任务
    
    类似于 enqueue_portrait_generation，但用于场景。
    """
    logger.info(f"[SceneAnchor] Enqueuing generation for {scene_name} ({scene_id})")
    
    # 自动创建 DB 会话
    local_db = None
    if db_session is None:
        from app.core.database import SessionLocal
        local_db = SessionLocal()
        db_session = local_db
    
    try:
        # 1. 构建 Spec
        spec = SceneAnchorSpec(
            scene_id=scene_id,
            name=scene_name,
            location=location or "generic interior",
            time_of_day=time_of_day or "day",
            mood=mood or "neutral"
        )
        
        # 2. 更新状态为 generating
        if db_session:
            await _update_scene_status(db_session, scene_id, "generating")
        
        # 3. 生成锚点
        success, anchor_path, meta = await generate_anchor_with_retry(
            spec=spec,
            provider=anchor_provider,
        )
        
        if not success:
            if db_session:
                await _update_scene_status(db_session, scene_id, "failed", meta.get("error"))
            return {"success": False, "scene_id": scene_id, "error": meta.get("error")}
        
        # 4. 提取 Control Maps
        control_result = await extract_control_maps(
            anchor_image_path=anchor_path,
            scene_id=scene_id,
            provider=control_map_provider,
        )
        
        # 5. 更新数据库
        if db_session:
            await _update_scene_anchor(
                db_session, 
                scene_id, 
                anchor_path, 
                control_result.maps if control_result.success else {},
                meta
            )
        
        # 6. 发送事件
        await _emit_anchor_ready(scene_id, anchor_path)
        
        return {
            "success": True,
            "scene_id": scene_id,
            "anchor_path": anchor_path,
            "control_maps": control_result.maps if control_result.success else {},
            "meta": meta
        }
        
    except Exception as e:
        logger.error(f"[SceneAnchor] Generation error: {e}")
        
        if db_session:
            await _update_scene_status(db_session, scene_id, "failed", str(e))
        
        return {"success": False, "scene_id": scene_id, "error": str(e)}
    finally:
        if local_db:
            local_db.close()


async def _update_scene_status(db, scene_id: str, status: str, error: str = None):
    """更新场景锚点状态"""
    from app.models.asset import Asset
    
    asset = db.query(Asset).filter(Asset.id == scene_id).first()
    if asset:
        data = asset.data_json or {}
        data["anchor_status"] = status
        if error:
            data["anchor_error"] = error
        asset.data_json = data
        db.commit()


async def _update_scene_anchor(db, scene_id: str, anchor_path: str, control_maps: dict, meta: dict):
    """更新场景锚点数据"""
    from app.models.asset import Asset
    
    asset = db.query(Asset).filter(Asset.id == scene_id).first()
    if asset:
        data = asset.data_json or {}
        data["anchor_image_path"] = anchor_path
        data["anchor_status"] = "ready"
        data["control_maps"] = control_maps
        data["control_map_status"] = "ready" if control_maps else "none"
        data["anchor_meta"] = meta
        asset.data_json = data
        db.commit()


async def _emit_anchor_ready(scene_id: str, anchor_path: str):
    """发送锚点就绪事件"""
    logger.info(f"[Event] scene_anchor_ready: {scene_id}")
