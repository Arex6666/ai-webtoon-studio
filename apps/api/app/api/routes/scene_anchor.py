"""
Scene Anchor API - 场景一致性管理路由
提供场景锚点生成和管理功能
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.models.asset import Asset
from app.services.scene_anchor import get_control_map_generator, get_anchor_storage

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Request/Response Models ============

class AnchorStatusResponse(BaseModel):
    """锚点状态响应"""
    asset_id: str
    status: str  # pending/generating/ready/failed
    has_anchor: bool = False
    has_depth: bool = False
    has_canny: bool = False
    has_lineart: bool = False
    message: Optional[str] = None


class AnchorUrlsResponse(BaseModel):
    """锚点 URL 响应"""
    asset_id: str
    anchor_url: Optional[str] = None
    depth_url: Optional[str] = None
    canny_url: Optional[str] = None
    lineart_url: Optional[str] = None


class GenerateAnchorResponse(BaseModel):
    """生成锚点响应"""
    asset_id: str
    status: str
    generated_maps: List[str]
    message: str


# ============ Routes ============

@router.post("/{asset_id}/generate-anchor", response_model=GenerateAnchorResponse)
async def generate_anchor(
    asset_id: str,
    file: UploadFile = File(..., description="空镜图像文件"),
    generate_depth: bool = True,
    generate_canny: bool = True,
    generate_lineart: bool = True,
    db: Session = Depends(get_db)
):
    """
    为场景生成锚点（控制图）
    
    上传空镜图像后，系统会自动生成：
    - Depth Map（深度图）- 用于空间结构锁定
    - Canny Edge（边缘图）- 用于轮廓锁定
    - Lineart（线稿图）- 用于线条风格锁定
    """
    # 检查资产是否存在且为场景类型
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset.type != "scene":
        raise HTTPException(
            status_code=400,
            detail=f"Asset type must be 'scene', got '{asset.type}'"
        )
    
    # 读取图像
    image_data = await file.read()
    if len(image_data) > 20 * 1024 * 1024:  # 20MB 限制
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")
    
    # 更新状态为 generating
    data_json = asset.data_json or {}
    data_json["anchor_status"] = "generating"
    asset.data_json = data_json
    db.commit()
    
    try:
        # 生成控制图
        generator = get_control_map_generator()
        control_maps = {}
        generated_types = []
        
        if generate_depth:
            try:
                control_maps["depth"] = generator.generate_depth(image_data)
                generated_types.append("depth")
            except Exception as e:
                logger.error(f"Failed to generate depth map: {e}")
        
        if generate_canny:
            try:
                control_maps["canny"] = generator.generate_canny(image_data)
                generated_types.append("canny")
            except Exception as e:
                logger.error(f"Failed to generate canny map: {e}")
        
        if generate_lineart:
            try:
                control_maps["lineart"] = generator.generate_lineart(image_data)
                generated_types.append("lineart")
            except Exception as e:
                logger.error(f"Failed to generate lineart map: {e}")
        
        if len(control_maps) == 0:
            data_json["anchor_status"] = "failed"
            data_json["anchor_error"] = "Failed to generate any control maps"
            asset.data_json = data_json
            db.commit()
            
            raise HTTPException(
                status_code=500,
                detail="Failed to generate any control maps"
            )
        
        # 获取图像尺寸
        width, height = generator.get_image_size(image_data)
        
        # 存储到 MinIO
        storage = get_anchor_storage()
        paths = await storage.save_anchor(
            scene_id=asset_id,
            anchor_image=image_data,
            control_maps=control_maps,
            metadata={
                "width": width,
                "height": height,
                "generated_maps": generated_types,
            }
        )
        
        # 更新资产元数据
        data_json["anchor_status"] = "ready"
        data_json["anchor_image"] = paths.get("anchor")
        data_json["control_maps"] = {
            k: v for k, v in paths.items() if k != "anchor"
        }
        data_json["anchor_size"] = {"width": width, "height": height}
        if "anchor_error" in data_json:
            del data_json["anchor_error"]
        asset.data_json = data_json
        db.commit()
        
        logger.info(f"Generated anchor for scene {asset_id}: {generated_types}")
        
        return GenerateAnchorResponse(
            asset_id=asset_id,
            status="ready",
            generated_maps=generated_types,
            message=f"Successfully generated {len(generated_types)} control maps"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate anchor for {asset_id}: {e}")
        
        data_json["anchor_status"] = "failed"
        data_json["anchor_error"] = str(e)
        asset.data_json = data_json
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Anchor generation failed: {str(e)}")


@router.get("/{asset_id}/anchor-status", response_model=AnchorStatusResponse)
async def get_anchor_status(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """获取场景的锚点状态"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    data_json = asset.data_json or {}
    control_maps = data_json.get("control_maps", {})
    
    return AnchorStatusResponse(
        asset_id=asset_id,
        status=data_json.get("anchor_status", "pending"),
        has_anchor=bool(data_json.get("anchor_image")),
        has_depth="depth" in control_maps,
        has_canny="canny" in control_maps,
        has_lineart="lineart" in control_maps,
        message=data_json.get("anchor_error")
    )


@router.get("/{asset_id}/anchor-urls", response_model=AnchorUrlsResponse)
async def get_anchor_urls(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """获取场景锚点的预签名 URL（用于前端预览）"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    data_json = asset.data_json or {}
    if data_json.get("anchor_status") != "ready":
        return AnchorUrlsResponse(asset_id=asset_id)
    
    storage = get_anchor_storage()
    urls = storage.get_all_urls(asset_id)
    
    return AnchorUrlsResponse(
        asset_id=asset_id,
        anchor_url=urls.get("anchor"),
        depth_url=urls.get("depth"),
        canny_url=urls.get("canny"),
        lineart_url=urls.get("lineart"),
    )


@router.get("/{asset_id}/control-map/{map_type}")
async def get_control_map(
    asset_id: str,
    map_type: str,
    db: Session = Depends(get_db)
):
    """
    获取指定类型的控制图
    
    map_type: depth / canny / lineart / anchor
    """
    if map_type not in ["depth", "canny", "lineart", "anchor"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid map type: {map_type}. Must be one of: depth, canny, lineart, anchor"
        )
    
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    storage = get_anchor_storage()
    
    if map_type == "anchor":
        data = await storage.load_anchor_image(asset_id)
    else:
        data = await storage.load_control_map(asset_id, map_type)
    
    if data is None:
        raise HTTPException(status_code=404, detail=f"{map_type} map not found")
    
    return Response(
        content=data,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={map_type}.png"}
    )


@router.delete("/{asset_id}/anchor")
async def delete_anchor(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """删除场景的锚点数据"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    storage = get_anchor_storage()
    await storage.delete_anchor(asset_id)
    
    # 更新资产元数据
    data_json = asset.data_json or {}
    data_json["anchor_status"] = "pending"
    for key in ["anchor_image", "control_maps", "anchor_size"]:
        if key in data_json:
            del data_json[key]
    asset.data_json = data_json
    db.commit()
    
    return {"message": "Anchor deleted", "asset_id": asset_id}


@router.post("/{asset_id}/regenerate-map/{map_type}", response_model=GenerateAnchorResponse)
async def regenerate_control_map(
    asset_id: str,
    map_type: str,
    db: Session = Depends(get_db)
):
    """
    重新生成单个控制图
    
    用于：用户觉得某个控制图效果不好时重新生成
    """
    if map_type not in ["depth", "canny", "lineart"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid map type: {map_type}"
        )
    
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # 加载原始空镜图像
    storage = get_anchor_storage()
    anchor_data = await storage.load_anchor_image(asset_id)
    
    if anchor_data is None:
        raise HTTPException(
            status_code=400,
            detail="No anchor image found. Please generate anchor first."
        )
    
    # 重新生成指定控制图
    generator = get_control_map_generator()
    
    try:
        if map_type == "depth":
            map_data = generator.generate_depth(anchor_data)
        elif map_type == "canny":
            map_data = generator.generate_canny(anchor_data)
        else:
            map_data = generator.generate_lineart(anchor_data)
        
        # 更新存储
        from app.core.storage import get_storage_client
        storage_client = get_storage_client()
        path = f"anchors/scenes/{asset_id}/{map_type}.png"
        await storage_client.upload_bytes(path, map_data, "image/png")
        
        # 更新元数据
        data_json = asset.data_json or {}
        if "control_maps" not in data_json:
            data_json["control_maps"] = {}
        data_json["control_maps"][map_type] = path
        asset.data_json = data_json
        db.commit()
        
        return GenerateAnchorResponse(
            asset_id=asset_id,
            status="ready",
            generated_maps=[map_type],
            message=f"Successfully regenerated {map_type} map"
        )
        
    except Exception as e:
        logger.error(f"Failed to regenerate {map_type} for {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")
