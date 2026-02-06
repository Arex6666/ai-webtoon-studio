"""
FaceID API Routes
Production MVP: Character face embedding extraction and management

Endpoints:
- POST /api/v1/faceid/extract - Extract face embedding from image
- POST /api/v1/assets/characters/{id}/set-ref - Set reference image and trigger extraction
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.database import get_db
from app.models.asset import Asset
from app.services.faceid.embedder import embed_character_faceid

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Request/Response Models ============

class ExtractFaceIDRequest(BaseModel):
    """FaceID 提取请求"""
    image_url: str
    character_id: Optional[str] = None
    project_id: Optional[str] = None
    provider: str = "auto"  # "mock", "insightface", or "auto"


class ExtractFaceIDResponse(BaseModel):
    """FaceID 提取响应"""
    success: bool
    embedding_path: Optional[str] = None
    embedding_status: str = "pending"
    meta: Optional[dict] = None
    error: Optional[str] = None


class SetReferenceImageRequest(BaseModel):
    """设置参考图请求"""
    ref_image_url: str
    auto_extract: bool = True  # 自动触发 FaceID 提取
    provider: str = "auto"


class CharacterAssetResponse(BaseModel):
    """角色资产响应"""
    id: str
    name: str
    ref_image_url: Optional[str] = None
    embedding_path: Optional[str] = None
    embedding_status: str = "missing"
    updated_at: str


# ============ API Endpoints ============

@router.post("/faceid/extract", response_model=ExtractFaceIDResponse)
async def extract_faceid(
    request: ExtractFaceIDRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    提取 FaceID embedding
    
    可传入角色 ID 自动更新数据库，或独立调用仅返回结果
    """
    logger.info(f"[FaceID API] Extract request: character={request.character_id}, url={request.image_url[:50]}...")
    
    try:
        # 执行提取
        result = await embed_character_faceid(
            character_id=request.character_id or "temp",
            reference_image_path=request.image_url,
            project_id=request.project_id or "default",
            provider_name=request.provider
        )
        
        if not result["success"]:
            return ExtractFaceIDResponse(
                success=False,
                embedding_status="failed",
                error=result.get("error"),
                meta=result.get("meta")
            )
        
        # 如果指定了角色 ID，更新数据库
        if request.character_id:
            asset = db.query(Asset).filter(
                Asset.id == request.character_id,
                Asset.type == "character"
            ).first()
            
            if asset:
                data_json = asset.data_json or {}
                data_json["embedding_path"] = result["embedding_path"]
                data_json["embedding_status"] = "ready"
                data_json["embedding_meta"] = result.get("meta", {})
                data_json["embedding_updated_at"] = datetime.utcnow().isoformat() + "Z"
                asset.data_json = data_json
                db.commit()
                logger.info(f"[FaceID API] Updated character {request.character_id} with embedding")
        
        return ExtractFaceIDResponse(
            success=True,
            embedding_path=result["embedding_path"],
            embedding_status="ready",
            meta=result.get("meta")
        )
        
    except Exception as e:
        logger.error(f"[FaceID API] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assets/characters/{character_id}/set-ref", response_model=CharacterAssetResponse)
async def set_character_reference(
    character_id: str,
    request: SetReferenceImageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    设置角色参考图并触发 FaceID 提取
    
    这是用户交互的主要入口：
    1. 保存参考图 URL
    2. 如果 auto_extract=True，后台提取 embedding
    3. 返回更新后的角色状态
    """
    asset = db.query(Asset).filter(
        Asset.id == character_id,
        Asset.type == "character"
    ).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Character asset not found")
    
    # 更新参考图
    data_json = asset.data_json or {}
    data_json["ref_image_url"] = request.ref_image_url
    data_json["embedding_status"] = "pending" if request.auto_extract else data_json.get("embedding_status", "missing")
    asset.data_json = data_json
    db.commit()
    
    # 后台提取 embedding
    if request.auto_extract:
        async def extract_task():
            try:
                result = await embed_character_faceid(
                    character_id=character_id,
                    reference_image_path=request.ref_image_url,
                    project_id=asset.project_id,
                    provider_name=request.provider
                )
                
                # 更新数据库
                from app.core.database import SessionLocal
                db_session = SessionLocal()
                try:
                    asset_update = db_session.query(Asset).filter(Asset.id == character_id).first()
                    if asset_update:
                        data = asset_update.data_json or {}
                        if result["success"]:
                            data["embedding_path"] = result["embedding_path"]
                            data["embedding_status"] = "ready"
                            data["embedding_meta"] = result.get("meta", {})
                        else:
                            data["embedding_status"] = "failed"
                            data["embedding_error"] = result.get("error")
                        data["embedding_updated_at"] = datetime.utcnow().isoformat() + "Z"
                        asset_update.data_json = data
                        db_session.commit()
                finally:
                    db_session.close()
                    
            except Exception as e:
                logger.error(f"[FaceID] Background extraction error: {e}")
        
        background_tasks.add_task(extract_task)
    
    return CharacterAssetResponse(
        id=asset.id,
        name=asset.name,
        ref_image_url=data_json.get("ref_image_url"),
        embedding_path=data_json.get("embedding_path"),
        embedding_status=data_json.get("embedding_status", "pending"),
        updated_at=datetime.utcnow().isoformat() + "Z"
    )


@router.get("/assets/characters/{character_id}/embedding-status")
async def get_embedding_status(
    character_id: str,
    db: Session = Depends(get_db)
):
    """
    获取角色 FaceID embedding 状态
    
    用于前端轮询检查提取进度
    """
    asset = db.query(Asset).filter(
        Asset.id == character_id,
        Asset.type == "character"
    ).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Character not found")
    
    data_json = asset.data_json or {}
    
    return {
        "character_id": character_id,
        "name": asset.name,
        "ref_image_url": data_json.get("ref_image_url"),
        "embedding_status": data_json.get("embedding_status", "missing"),
        "embedding_path": data_json.get("embedding_path"),
        "embedding_meta": data_json.get("embedding_meta"),
        "error": data_json.get("embedding_error")
    }
