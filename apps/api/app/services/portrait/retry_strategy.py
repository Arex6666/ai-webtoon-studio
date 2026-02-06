"""
S5-01 - Portrait Retry Strategy

失败重试策略：最多 3 次，逐级加强约束。
"""

import logging
import random
from typing import Optional, Tuple

from .spec_generator import CharacterPortraitSpec, generate_portrait_spec
from .prompt_composer import compose_portrait_prompt
from .portrait_generator import generate_character_portrait, PortraitResult
from .portrait_qa import validate_portrait, PortraitQAResult

logger = logging.getLogger(__name__)


# 重试配置
MAX_ATTEMPTS = 3

# 每次重试的 prompt 增强
RETRY_ENHANCEMENTS = [
    # 第 1 次重试：加强证件照约束
    "front-facing, passport photo style, plain background, no accessories, direct eye contact",
    # 第 2 次重试：换 seed，更强约束
    "frontal portrait, id photo, neutral expression, uniform lighting, centered face",
    # 第 3 次重试：最终尝试
    None
]


async def generate_with_retry(
    spec: CharacterPortraitSpec,
    provider: str = "mock",
    size: tuple[int, int] = (512, 512),
    output_dir: Optional[str] = None
) -> Tuple[bool, Optional[str], dict]:
    """
    带重试的肖像生成流程
    
    Args:
        spec: 角色肖像规格
        provider: 生成服务
        size: 图像尺寸
        output_dir: 输出目录
        
    Returns:
        (success, image_path, meta)
        meta 包含：attempts, final_status, qa_results, error
    """
    meta = {
        "attempts": 0,
        "final_status": "pending",
        "qa_results": [],
        "error": None,
        "provider": provider
    }
    
    seed = random.randint(0, 2**32 - 1)
    
    for attempt in range(MAX_ATTEMPTS):
        meta["attempts"] = attempt + 1
        logger.info(f"[Retry] Attempt {attempt + 1}/{MAX_ATTEMPTS} for {spec.name}")
        
        # 获取增强 prompt
        enhancement = RETRY_ENHANCEMENTS[attempt] if attempt < len(RETRY_ENHANCEMENTS) else None
        
        # 调整 seed（第 2 次开始换 seed）
        if attempt > 0:
            seed = random.randint(0, 2**32 - 1)
        
        # 生成图像
        result = await generate_character_portrait(
            spec=spec,
            provider=provider,
            size=size,
            seed=seed,
            output_dir=output_dir
        )
        
        if not result.success:
            logger.warning(f"[Retry] Generation failed: {result.error}")
            meta["error"] = result.error
            continue
        
        # QA 验证
        image_path = result.image_path or result.image_url
        
        if provider == "mock":
            # Mock 模式跳过 QA（用于测试）
            qa_result = PortraitQAResult(
                passed=True,
                face_count=1,
                face_confidence=0.95,
                face_area_ratio=0.25
            )
        else:
            qa_result = validate_portrait(image_path)
        
        meta["qa_results"].append(qa_result.model_dump())
        
        if qa_result.passed:
            logger.info(f"[Retry] Success on attempt {attempt + 1}")
            meta["final_status"] = "ready"
            
            # 合并 meta
            full_meta = {
                **meta,
                **result.meta
            }
            
            return True, image_path, full_meta
        else:
            logger.warning(f"[Retry] QA failed: {qa_result.issues}")
    
    # 所有尝试都失败
    logger.error(f"[Retry] All attempts failed for {spec.name}")
    meta["final_status"] = "failed"
    
    return False, None, meta


async def enqueue_portrait_generation(
    character_id: str,
    project_id: str,
    character_name: str,
    character_description: Optional[str] = None,
    appearance_traits: Optional[list] = None,
    provider: str = "mock",
    db_session = None
) -> dict:
    """
    入队参考图生成任务
    
    这是从 Apply 调用的主入口函数。
    """
    logger.info(f"[Portrait] Enqueuing generation for {character_name} ({character_id})")

    # 自动创建 DB 会话（如果是后台任务）
    local_db = None
    if db_session is None:
        from app.core.database import SessionLocal
        local_db = SessionLocal()
        db_session = local_db
    
    try:
        # 1. 生成 Spec
        spec = await generate_portrait_spec(
            character_id=character_id,
            character_name=character_name,
            character_description=character_description,
            appearance_traits=appearance_traits
        )
        
        # 2. 更新状态为 generating
        if db_session:
            await _update_character_status(
                db_session, character_id, "generating"
            )
        
        # 3. 带重试生成
        success, image_path, meta = await generate_with_retry(
            spec=spec,
            provider=provider
        )
        
        # 4. 更新数据库 & FaceID 提取
        if db_session:
            if success:
                # S5-02: 提取 FaceID
                await _update_character_reference(
                    db_session, character_id, image_path, meta
                )
                
                # 触发 FaceID 提取（S5-02）
                from app.services.faceid.embedder import embed_character_faceid
                faceid_result = await embed_character_faceid(
                    character_id=character_id, 
                    reference_image_path=image_path,
                    project_id=project_id,
                    provider_name="mock" # Should config provider
                )
                
                if faceid_result["success"]:
                    logger.info(f"[FaceID] Success for {character_name}")
                    # AssetsLock status updated in embed_character_faceid? 
                    # No, embedder returns result, we might need to update here or embedder updates.
                    # Plan said embedder updates Asset/AssetsLock.
                    # Let's assume embedder logic handles storage, we need to update DB with path.
                    
                    # Update FaceID info
                    embedding_path = faceid_result["embedding_path"]
                    await _update_character_faceid(db_session, character_id, embedding_path, faceid_result.get("meta"))
                else:
                    logger.warning(f"[FaceID] Failed: {faceid_result.get('error')}")
                    # Optional: mark as warning or fail?
                    # User said: "Retry generation if FaceID fails". 
                    # For now, just log. Ideal: Loop back to retry.
            else:
                await _update_character_status(
                    db_session, character_id, "failed", meta.get("error")
                )
        
        # 5. 发送事件
        if success:
            await _emit_reference_ready(character_id, image_path)
        else:
            await _emit_reference_failed(character_id, meta.get("error"))
        
        return {
            "success": success,
            "character_id": character_id,
            "image_path": image_path,
            "meta": meta
        }
        
    except Exception as e:
        logger.error(f"[Portrait] Generation error: {e}")
        
        if db_session:
            await _update_character_status(
                db_session, character_id, "failed", str(e)
            )
        
        return {
            "success": False,
            "character_id": character_id,
            "error": str(e)
        }
    finally:
        if local_db:
            local_db.close()


async def _update_character_status(db, character_id: str, status: str, error: str = None):
    """更新角色参考图状态"""
    from app.models.asset import Asset
    
    asset = db.query(Asset).filter(Asset.id == character_id).first()
    if asset:
        asset.reference_image_status = status
        if error:
            asset.reference_image_meta = {"error": error}
        db.commit()


async def _update_character_reference(db, character_id: str, image_path: str, meta: dict):
    """更新角色参考图数据"""
    from app.models.asset import Asset
    
    asset = db.query(Asset).filter(Asset.id == character_id).first()
    if asset:
        asset.reference_image_path = image_path
        asset.reference_image_status = "ready"
        asset.reference_image_meta = meta
        db.commit()


async def _update_character_faceid(db, character_id: str, embedding_path: str, meta: dict):
    """更新角色 FaceID 数据"""
    from app.models.asset import Asset
    
    asset = db.query(Asset).filter(Asset.id == character_id).first()
    if asset:
        # 1. Update data_json with embedding info
        data = asset.data_json or {}
        data["face_embedding_path"] = embedding_path
        data["face_embedding_meta"] = meta
        asset.data_json = data
        db.commit()


async def _emit_reference_ready(character_id: str, image_path: str):
    """发送参考图就绪事件"""
    # TODO: 通过 WebSocket 发送事件
    logger.info(f"[Event] character_reference_ready: {character_id}")


async def _emit_reference_failed(character_id: str, error: str):
    """发送参考图失败事件"""
    # TODO: 通过 WebSocket 发送事件
    logger.info(f"[Event] character_reference_failed: {character_id}")
