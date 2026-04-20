"""
Consistency-related asset routes (FaceID embeddings, scene anchors)
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import ConfigDict, BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.storage import storage_client
from app.models.asset import Asset
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


# Request/Response Models
class AssetResponse(BaseModel):
    id: str
    project_id: str
    name: str
    type: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    data_json: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes = True)

@router.post("/{asset_id}/upload-image")
async def upload_asset_image(
    asset_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    前端专用: 上传资产参考图/缩略图
    自动判断: 如果没有缩略图则设为缩略图, 总是添加到参考图列表
    """
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # 读取文件
    content = await file.read()

    # 上传到存储
    folder = f"assets/{asset.project_id}/{asset.type}/{asset_id}"
    try:
        path = storage_client.upload_file(
            data=content,
            filename=file.filename,
            content_type=file.content_type,
            folder=folder
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Storage error: {str(e)}")

    # 获取 URL
    url = storage_client.get_url(path)

    # 更新资产数据
    data = asset.data_json or {}

    # 总是更新 thumbnail 如果为空
    if not asset.thumbnail_url:
        asset.thumbnail_url = url

    # 添加到参考图
    if "reference_images" not in data:
        data["reference_images"] = []

    # 避免重复
    if url not in data["reference_images"]:
        data["reference_images"].append(url)

    # 如果是场景且没有 anchor_image
    if asset.type == "scene" and not data.get("anchor_image"):
        data["anchor_image"] = url

    asset.data_json = data
    db.commit()

    return {
        "success": True,
        "image_url": url,
        "message": "Image uploaded successfully"
    }


@router.post("/{asset_id}/generate-description")
async def generate_asset_description(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    使用 LLM 生成/完善资产描述
    """
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    from app.services.brain.standard_llm import StandardLLMService

    llm = StandardLLMService()
    data = asset.data_json or {}

    prompt = f"""
    You are a creative writing assistant for a webtoon studio.
    Please write a concise but vivid visual description for this {asset.type}.

    Name: {asset.name}
    Current Description: {asset.description or "None"}
    Traits: {', '.join(data.get('appearance_traits', []))}

    The description should be suitable for visual reference for an artist or AI image generator.
    Keep it under 100 words. Language: Chinese.
    """

    try:
        description = await llm._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        # Clean up quotes if any
        description = description.strip().strip('"').strip("'")

        # Update asset
        asset.description = description
        db.commit()

        return {
            "success": True,
            "description": description
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
