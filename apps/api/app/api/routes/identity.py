"""
Identity API - 角色一致性管理路由
提供 FaceID Embedding 提取和管理功能
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.models.asset import Asset
from app.services.identity import get_face_extractor, get_embedding_storage

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Request/Response Models ============

class EmbeddingStatusResponse(BaseModel):
    """Embedding 状态响应"""
    asset_id: str
    status: str  # pending/extracting/ready/failed
    embedding_path: Optional[str] = None
    source_image_count: int = 0
    message: Optional[str] = None


class EmbeddingExtractRequest(BaseModel):
    """提取请求（用于已有图片）"""
    image_paths: List[str]


class SimilarityResponse(BaseModel):
    """相似度检测响应"""
    similarity: float
    is_match: bool
    threshold: float


# ============ Routes ============

@router.post("/{asset_id}/extract-embedding", response_model=EmbeddingStatusResponse)
async def extract_embedding(
    asset_id: str,
    files: List[UploadFile] = File(..., description="定妆照文件（建议正面+侧面+表情）"),
    db: Session = Depends(get_db)
):
    """
    为角色提取 FaceID Embedding
    
    建议上传 3-5 张定妆照：
    - 1 张正面照
    - 1 张侧面照
    - 2-3 张不同表情
    
    系统会自动平均多张图的 embedding，提高稳定性。
    """
    # 检查资产是否存在且为角色类型
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset.type != "character":
        raise HTTPException(
            status_code=400, 
            detail=f"Asset type must be 'character', got '{asset.type}'"
        )
    
    # 读取所有图片
    image_data_list = []
    for f in files:
        content = await f.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB 限制
            raise HTTPException(status_code=400, detail=f"File {f.filename} too large (max 10MB)")
        image_data_list.append(content)
    
    if len(image_data_list) == 0:
        raise HTTPException(status_code=400, detail="No images provided")
    
    # 更新状态为 extracting
    data_json = asset.data_json or {}
    data_json["embedding_status"] = "extracting"
    asset.data_json = data_json
    db.commit()
    
    try:
        # 提取 embedding
        extractor = get_face_extractor()
        
        if len(image_data_list) == 1:
            embedding, bbox_info = extractor.extract_embedding(image_data_list[0])
        else:
            embedding = extractor.extract_from_multiple(image_data_list)
            bbox_info = None
        
        if embedding is None:
            # 提取失败
            data_json["embedding_status"] = "failed"
            data_json["embedding_error"] = "No face detected in images"
            asset.data_json = data_json
            db.commit()
            
            return EmbeddingStatusResponse(
                asset_id=asset_id,
                status="failed",
                source_image_count=len(image_data_list),
                message="No face detected in any of the provided images"
            )
        
        # 序列化 embedding
        embedding_data = extractor.serialize_embedding(embedding)
        
        # 存储到 MinIO
        storage = get_embedding_storage()
        embedding_path = await storage.save_embedding(
            character_id=asset_id,
            embedding_data=embedding_data,
            metadata={
                "source_image_count": len(image_data_list),
                "embedding_dim": embedding.shape[0],
            }
        )
        
        # 更新资产元数据
        data_json["embedding_status"] = "ready"
        data_json["embedding_path"] = embedding_path
        data_json["embedding_source_count"] = len(image_data_list)
        if "embedding_error" in data_json:
            del data_json["embedding_error"]
        asset.data_json = data_json
        db.commit()
        
        logger.info(f"Extracted embedding for character {asset_id} from {len(image_data_list)} images")
        
        return EmbeddingStatusResponse(
            asset_id=asset_id,
            status="ready",
            embedding_path=embedding_path,
            source_image_count=len(image_data_list),
            message=f"Successfully extracted embedding from {len(image_data_list)} images"
        )
        
    except Exception as e:
        logger.error(f"Failed to extract embedding for {asset_id}: {e}")
        
        # 更新状态为失败
        data_json["embedding_status"] = "failed"
        data_json["embedding_error"] = str(e)
        asset.data_json = data_json
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Embedding extraction failed: {str(e)}")


@router.get("/{asset_id}/embedding-status", response_model=EmbeddingStatusResponse)
async def get_embedding_status(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """获取角色的 Embedding 状态"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    data_json = asset.data_json or {}
    
    return EmbeddingStatusResponse(
        asset_id=asset_id,
        status=data_json.get("embedding_status", "pending"),
        embedding_path=data_json.get("embedding_path"),
        source_image_count=data_json.get("embedding_source_count", 0),
        message=data_json.get("embedding_error")
    )


@router.delete("/{asset_id}/embedding")
async def delete_embedding(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """删除角色的 Embedding"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    storage = get_embedding_storage()
    await storage.delete_embedding(asset_id)
    
    # 更新资产元数据
    data_json = asset.data_json or {}
    data_json["embedding_status"] = "pending"
    if "embedding_path" in data_json:
        del data_json["embedding_path"]
    if "embedding_source_count" in data_json:
        del data_json["embedding_source_count"]
    asset.data_json = data_json
    db.commit()
    
    return {"message": "Embedding deleted", "asset_id": asset_id}


@router.post("/compare-similarity", response_model=SimilarityResponse)
async def compare_similarity(
    file1: UploadFile = File(..., description="第一张图片"),
    file2: UploadFile = File(..., description="第二张图片"),
    threshold: float = 0.6
):
    """
    比较两张图片中人脸的相似度
    
    用于：
    - 检测生成结果是否与角色一致
    - QA 脸漂移检测
    """
    # 读取图片
    img1_data = await file1.read()
    img2_data = await file2.read()
    
    extractor = get_face_extractor()
    
    # 提取 embedding
    emb1, _ = extractor.extract_embedding(img1_data)
    emb2, _ = extractor.extract_embedding(img2_data)
    
    if emb1 is None or emb2 is None:
        raise HTTPException(
            status_code=400, 
            detail="Could not detect face in one or both images"
        )
    
    # 计算相似度
    similarity = extractor.compute_similarity(emb1, emb2)
    
    return SimilarityResponse(
        similarity=similarity,
        is_match=similarity >= threshold,
        threshold=threshold
    )


@router.post("/{asset_id}/check-consistency", response_model=SimilarityResponse)
async def check_consistency(
    asset_id: str,
    file: UploadFile = File(..., description="待检测的图片"),
    threshold: float = 0.6,
    db: Session = Depends(get_db)
):
    """
    检测图片与角色 embedding 的一致性
    
    用于 QA 流程：检测生成的图片是否与角色定妆照一致
    """
    # 获取角色 embedding
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    data_json = asset.data_json or {}
    if data_json.get("embedding_status") != "ready":
        raise HTTPException(
            status_code=400, 
            detail="Character embedding not ready. Please extract embedding first."
        )
    
    # 加载存储的 embedding
    storage = get_embedding_storage()
    stored_emb_data = await storage.load_embedding(asset_id)
    
    if stored_emb_data is None:
        raise HTTPException(status_code=404, detail="Embedding file not found")
    
    extractor = get_face_extractor()
    stored_embedding = extractor.deserialize_embedding(stored_emb_data)
    
    # 从上传图片提取 embedding
    img_data = await file.read()
    current_embedding, _ = extractor.extract_embedding(img_data)
    
    if current_embedding is None:
        raise HTTPException(status_code=400, detail="Could not detect face in image")
    
    # 计算相似度
    similarity = extractor.compute_similarity(stored_embedding, current_embedding)
    
    return SimilarityResponse(
        similarity=similarity,
        is_match=similarity >= threshold,
        threshold=threshold
    )
