"""
资产管理路由
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.storage import storage_client
from app.models.asset import Asset, AssetType
from app.models.project import Project
from app.services.portrait.retry_strategy import enqueue_portrait_generation

router = APIRouter()


# Request/Response Models
class AssetCreate(BaseModel):
    project_id: str
    name: str
    type: str  # character/scene/bubble/style/effect
    description: Optional[str] = None
    data_json: Optional[Dict[str, Any]] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


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

    class Config:
        from_attributes = True


class AssetListResponse(BaseModel):
    items: List[AssetResponse]
    total: int


# Routes
@router.get("/project/{project_id}", response_model=AssetListResponse)
async def list_assets(
    project_id: str,
    asset_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取项目的所有资产"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    query = db.query(Asset).filter(
        Asset.project_id == project_id,
        Asset.status == "active"
    )
    
    if asset_type:
        query = query.filter(Asset.type == asset_type)
    
    assets = query.order_by(Asset.created_at.desc()).all()
    
    items = [
        AssetResponse(
            id=a.id,
            project_id=a.project_id,
            name=a.name,
            type=a.type,
            description=a.description,
            thumbnail_url=a.thumbnail_url,
            data_json=a.data_json or {},
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at
        )
        for a in assets
    ]
    
    return AssetListResponse(items=items, total=len(items))


@router.post("", response_model=AssetResponse)
async def create_asset(
    request: AssetCreate,
    db: Session = Depends(get_db)
):
    """创建资产"""
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 验证资产类型
    valid_types = ["character", "scene", "bubble", "style", "effect"]
    if request.type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid asset type. Must be one of: {valid_types}")
    
    asset = Asset(
        project_id=request.project_id,
        name=request.name,
        type=request.type,
        description=request.description,
        data_json=request.data_json or {}
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return AssetResponse(
        id=asset.id,
        project_id=asset.project_id,
        name=asset.name,
        type=asset.type,
        description=asset.description,
        thumbnail_url=asset.thumbnail_url,
        data_json=asset.data_json,
        status=asset.status,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """获取资产详情"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    return AssetResponse(
        id=asset.id,
        project_id=asset.project_id,
        name=asset.name,
        type=asset.type,
        description=asset.description,
        thumbnail_url=asset.thumbnail_url,
        data_json=asset.data_json or {},
        status=asset.status,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    request: AssetUpdate,
    db: Session = Depends(get_db)
):
    """更新资产"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if request.name is not None:
        asset.name = request.name
    if request.description is not None:
        asset.description = request.description
    if request.data_json is not None:
        asset.data_json = request.data_json
    if request.status is not None:
        asset.status = request.status
    
    db.commit()
    db.refresh(asset)
    
    return AssetResponse(
        id=asset.id,
        project_id=asset.project_id,
        name=asset.name,
        type=asset.type,
        description=asset.description,
        thumbnail_url=asset.thumbnail_url,
        data_json=asset.data_json,
        status=asset.status,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.post("/{asset_id}/upload")
async def upload_asset_file(
    asset_id: str,
    file: UploadFile = File(...),
    file_type: str = Form("reference"),  # reference/thumbnail/anchor
    db: Session = Depends(get_db)
):
    """上传资产文件"""
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
        raise HTTPException(status_code=503, detail="Storage not available")

    # 获取 URL
    url = storage_client.get_url(path)
    
    # 更新资产数据
    data = asset.data_json or {}
    
    if file_type == "thumbnail":
        asset.thumbnail_url = url  # 存可访问 URL，前端可直接渲染
    elif file_type == "reference":
        if "reference_images" not in data:
            data["reference_images"] = []
        data["reference_images"].append(url)  # 统一存 URL
    elif file_type == "anchor":
        data["anchor_image"] = url  # 统一存 URL
    
    asset.data_json = data
    db.commit()
    
    return {
        "message": "File uploaded",
        "path": path,
        "url": url
    }


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """删除资产（软删除）"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    asset.status = "archived"
    db.commit()
    
    return {"message": "Asset archived", "id": asset_id}


# 预设资产创建
@router.post("/preset/character")
async def create_character_preset(
    project_id: str,
    name: str,
    description: str = "",
    db: Session = Depends(get_db)
):
    """创建角色预设"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    asset = Asset(
        project_id=project_id,
        name=name,
        type="character",
        description=description,
        data_json={
            "reference_images": [],
            "face_embedding": None,
            "consistency_prompt": f"character named {name}",
            "default_emotion": "neutral"
        }
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return {"message": "Character created", "id": asset.id}


@router.post("/preset/bubble-style")
async def create_bubble_style_preset(
    project_id: str,
    name: str,
    style_type: str = "normal",
    db: Session = Depends(get_db)
):
    """创建气泡样式预设"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 预设 SVG 模板
    svg_templates = {
        "normal": '<ellipse cx="50%" cy="50%" rx="45%" ry="40%" fill="white" stroke="black" stroke-width="2"/>',
        "shout": '<polygon points="50,5 95,30 85,95 15,95 5,30" fill="white" stroke="black" stroke-width="3"/>',
        "thought": '<ellipse cx="50%" cy="40%" rx="40%" ry="30%" fill="white" stroke="black" stroke-width="2"/><circle cx="30%" cy="80%" r="8%" fill="white" stroke="black"/><circle cx="20%" cy="90%" r="5%" fill="white" stroke="black"/>',
        "narration": '<rect x="5%" y="5%" width="90%" height="90%" fill="rgba(0,0,0,0.8)" rx="5"/>',
    }
    
    asset = Asset(
        project_id=project_id,
        name=name,
        type="bubble",
        data_json={
            "style_type": style_type,
            "svg_template": svg_templates.get(style_type, svg_templates["normal"]),
            "default_font": "Noto Sans SC",
            "default_font_size": 24,
            "text_color": "#000000" if style_type != "narration" else "#FFFFFF",
            "padding": {"top": 15, "right": 20, "bottom": 15, "left": 20}
        }
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return {"message": "Bubble style created", "id": asset.id}


@router.post("/{asset_id}/regenerate-reference")
async def regenerate_asset_reference(
    asset_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """重新生成资产参考图"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset.type != "character":
        raise HTTPException(status_code=400, detail="Only character assets support reference generation")
    
    # 提取描述信息
    data = asset.data_json or {}
    traits = data.get("appearance_traits", [])
    
    # Update status immediately
    asset.reference_image_status = "generating"
    db.commit()
    
    # Trigger generation
    background_tasks.add_task(
        enqueue_portrait_generation,
        character_id=asset.id,
        project_id=asset.project_id,
        character_name=asset.name,
        character_description=asset.description,
        appearance_traits=traits,
        provider="mock",
        db_session=None
    )
    
    return {"message": "Generation started", "status": "generating"}


@router.post("/{asset_id}/regenerate-anchor")
async def regenerate_asset_anchor(
    asset_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """S5-SC: 重新生成场景锚点图"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset.type != "scene":
        raise HTTPException(status_code=400, detail="Only scene assets support anchor generation")
    
    # 提取场景信息
    data = asset.data_json or {}
    
    # Update status immediately
    data["anchor_status"] = "generating"
    asset.data_json = data
    db.commit()
    
    # Trigger generation
    from app.services.scene.retry_strategy import enqueue_scene_anchor_generation
    
    background_tasks.add_task(
        enqueue_scene_anchor_generation,
        scene_id=asset.id,
        project_id=asset.project_id,
        scene_name=asset.name,
        location=data.get("location"),
        time_of_day=data.get("time_of_day"),
        mood=data.get("mood"),
        provider="mock",
        db_session=None
    )
    
    return {"message": "Anchor generation started", "status": "generating"}


class ClearAssetsRequest(BaseModel):
    """清空资产请求"""
    keep_types: List[str] = []  # 要保留的资产类型，如 ["style"]
    hard_delete: bool = False  # 是否硬删除（否则软删除）


@router.delete("/project/{project_id}/clear")
async def clear_project_assets(
    project_id: str,
    request: ClearAssetsRequest,
    db: Session = Depends(get_db)
):
    """
    清空项目的所有资产
    
    - keep_types: 要保留的资产类型
    - hard_delete: True=永久删除, False=归档
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 清空 PropAssets
    from app.models.prop_asset import PropAsset
    prop_count = db.query(PropAsset).filter(
        PropAsset.project_id == project_id
    ).delete()
    
    # 清空 AssetRelations
    from app.models.asset_relation import AssetRelation
    rel_count = db.query(AssetRelation).filter(
        AssetRelation.project_id == project_id
    ).delete()
    
    # 清空 OutfitVariants
    from app.models.outfit_variant import OutfitVariant
    char_ids = [a.id for a in db.query(Asset).filter(
        Asset.project_id == project_id,
        Asset.type == "character"
    ).all()]
    outfit_count = 0
    if char_ids:
        outfit_count = db.query(OutfitVariant).filter(
            OutfitVariant.character_asset_id.in_(char_ids)
        ).delete(synchronize_session=False)
    
    # 清空 Assets
    query = db.query(Asset).filter(Asset.project_id == project_id)
    if request.keep_types:
        query = query.filter(Asset.type.notin_(request.keep_types))
    
    if request.hard_delete:
        asset_count = query.delete(synchronize_session=False)
    else:
        asset_count = query.update({"status": "archived"}, synchronize_session=False)
    
    db.commit()
    
    return {
        "message": "Assets cleared",
        "deleted": {
            "assets": asset_count,
            "props": prop_count,
            "outfits": outfit_count,
            "relations": rel_count
        },
        "kept_types": request.keep_types
    }


class GenerateImageRequest(BaseModel):
    """生成资产图片请求"""
    style_hint: str = "韩漫风格"


@router.post("/{asset_id}/generate-image")
async def generate_asset_image(
    asset_id: str,
    request: GenerateImageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    使用豆包 AI 生成资产参考图
    
    - 角色: 生成定妆照 (正面半身像, 清晰脸部)
    - 场景: 生成空镜图 (无人背景)
    """
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset.type not in ["character", "scene"]:
        raise HTTPException(status_code=400, detail="Only character and scene assets support image generation")
    
    # 导入豆包生成器
    from app.services.doubao_asset_generator import (
        get_doubao_asset_generator,
        CharacterInfo,
        SceneInfo,
    )
    
    generator = get_doubao_asset_generator()
    if not generator:
        raise HTTPException(
            status_code=503, 
            detail="豆包服务未配置 (缺少 DOUBAO_API_KEY)"
        )
    
    data = asset.data_json or {}
    
    if asset.type == "character":
        # 构建角色信息
        character = CharacterInfo(
            name=asset.name,
            gender=data.get("gender"),
            age_range=data.get("age_range"),
            appearance_keywords=data.get("appearance_traits", []),
            personality_keywords=data.get("personality_traits", []),
        )
        
        # 同步生成 (或改为 background_tasks)
        result = await generator.generate_character_portrait(
            character=character,
            project_id=asset.project_id,
            asset_id=asset.id,
            style_hint=request.style_hint,
        )
        
        if result["success"]:
            # 更新资产
            if "reference_images" not in data:
                data["reference_images"] = []
            data["reference_images"].append(result["image_url"])
            if result.get("embedding_path"):
                data["face_embedding"] = result["embedding_path"]
            asset.data_json = data
            asset.thumbnail_url = result["image_url"]
            db.commit()
        
        return result
    
    elif asset.type == "scene":
        # 构建场景信息
        scene = SceneInfo(
            name=asset.name,
            description=data.get("anchor_hint", asset.description or ""),
            time_of_day=data.get("time_of_day"),
            lighting=data.get("lighting"),
            mood=data.get("mood"),
        )
        
        result = await generator.generate_scene_background(
            scene=scene,
            project_id=asset.project_id,
            asset_id=asset.id,
            style_hint=request.style_hint,
        )
        
        if result["success"]:
            data["anchor_image"] = result["image_url"]
            if "reference_images" not in data:
                data["reference_images"] = []
            data["reference_images"].append(result["image_url"])
            asset.data_json = data
            asset.thumbnail_url = result["image_url"]
            db.commit()
        
        return result


@router.post("/{asset_id}/upload-image")
async def upload_asset_image(
    asset_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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
