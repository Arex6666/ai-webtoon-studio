"""
Prop Assets API Routes
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.prop_asset import PropAsset, PropCategory
from app.models.outfit_variant import OutfitVariant
from app.models.asset import Asset
from app.models.asset_relation import AssetRelation, RelationType
from app.schemas.props import (
    PropAssetCreate, PropAssetUpdate, PropAssetResponse,
    OutfitVariantCreate, OutfitVariantUpdate, OutfitVariantResponse,
    AssetRelationCreate, AssetRelationResponse
)

router = APIRouter()


# ==========================================
# Prop Assets Endpoints
# ==========================================

@router.get("/projects/{project_id}/props", response_model=List[PropAssetResponse])
def list_props(
    project_id: str,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List props for a project, optionally filtered by category"""
    query = db.query(PropAsset).filter(PropAsset.project_id == project_id)
    if category:
        query = query.filter(PropAsset.category == category)
    return query.all()


@router.post("/props", response_model=PropAssetResponse)
def create_prop(
    request: PropAssetCreate,
    db: Session = Depends(get_db)
):
    """Create a new prop asset"""
    prop = PropAsset(
        project_id=request.project_id,
        canonical_name=request.canonical_name,
        category=request.category,
        visual_brief=request.visual_brief,
        material=request.material,
        colors=request.colors,
        shape=request.shape,
        key_features=request.key_features,
        aliases=request.aliases,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("/props/{prop_id}", response_model=PropAssetResponse)
def get_prop(
    prop_id: str,
    db: Session = Depends(get_db)
):
    """Get prop details"""
    prop = db.query(PropAsset).filter(PropAsset.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Prop asset not found")
    return prop


@router.put("/props/{prop_id}", response_model=PropAssetResponse)
def update_prop(
    prop_id: str,
    request: PropAssetUpdate,
    db: Session = Depends(get_db)
):
    """Update prop details"""
    prop = db.query(PropAsset).filter(PropAsset.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Prop asset not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prop, field, value)
    
    db.commit()
    db.refresh(prop)
    return prop


@router.delete("/props/{prop_id}")
def delete_prop(
    prop_id: str,
    db: Session = Depends(get_db)
):
    """Delete a prop asset"""
    prop = db.query(PropAsset).filter(PropAsset.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Prop asset not found")
    
    db.delete(prop)
    db.commit()
    return {"ok": True}


# ==========================================
# Outfit Variant Endpoints
# ==========================================

@router.get("/characters/{character_id}/outfits", response_model=List[OutfitVariantResponse])
def list_outfits(
    character_id: str,
    db: Session = Depends(get_db)
):
    """List outfit variants for a character"""
    return db.query(OutfitVariant).filter(OutfitVariant.character_asset_id == character_id).all()


@router.post("/outfits", response_model=OutfitVariantResponse)
def create_outfit(
    request: OutfitVariantCreate,
    db: Session = Depends(get_db)
):
    """Create a new outfit variant"""
    # Verify character exists
    char = db.query(Asset).filter(Asset.id == request.character_asset_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character asset not found")

    outfit = OutfitVariant(
        character_asset_id=request.character_asset_id,
        outfit_name=request.outfit_name,
        outfit_description=request.outfit_description,
        garment_items=request.garment_items,
        colors=request.colors,
        materials=request.materials,
        outfit_prompt=request.outfit_prompt,
        is_default=request.is_default
    )
    
    # If set as default, unset others
    if request.is_default:
        db.query(OutfitVariant).filter(
            OutfitVariant.character_asset_id == request.character_asset_id
        ).update({"is_default": False})
    
    db.add(outfit)
    db.commit()
    db.refresh(outfit)
    return outfit


@router.put("/outfits/{outfit_id}", response_model=OutfitVariantResponse)
def update_outfit(
    outfit_id: str,
    request: OutfitVariantUpdate,
    db: Session = Depends(get_db)
):
    """Update outfit details"""
    outfit = db.query(OutfitVariant).filter(OutfitVariant.id == outfit_id).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Outfit variant not found")
    
    update_data = request.model_dump(exclude_unset=True)
    
    # Handle default flag logic
    if update_data.get("is_default") is True:
        db.query(OutfitVariant).filter(
            OutfitVariant.character_asset_id == outfit.character_asset_id,
            OutfitVariant.id != outfit_id
        ).update({"is_default": False})

    for field, value in update_data.items():
        setattr(outfit, field, value)
    
    db.commit()
    db.refresh(outfit)
    return outfit


@router.delete("/outfits/{outfit_id}")
def delete_outfit(
    outfit_id: str,
    db: Session = Depends(get_db)
):
    """Delete an outfit variant"""
    outfit = db.query(OutfitVariant).filter(OutfitVariant.id == outfit_id).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Outfit variant not found")
    
    db.delete(outfit)
    db.commit()
    return {"ok": True}


# ==========================================
# Asset Relation Endpoints
# ==========================================

@router.post("/relations", response_model=AssetRelationResponse)
def create_relation(
    request: AssetRelationCreate,
    db: Session = Depends(get_db)
):
    """Create a relationship between assets"""
    relation = AssetRelation(
        project_id=request.project_id,
        chapter_id=request.chapter_id,
        relation_type=request.relation_type,
        subject_id=request.subject_id,
        subject_type=request.subject_type,
        object_id=request.object_id,
        object_type=request.object_type,
        relation_metadata=request.metadata
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.get("/projects/{project_id}/relations", response_model=List[AssetRelationResponse])
def list_relations(
    project_id: str,
    chapter_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    relation_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List asset relations with filters"""
    query = db.query(AssetRelation).filter(AssetRelation.project_id == project_id)
    
    if chapter_id:
        query = query.filter(AssetRelation.chapter_id == chapter_id)
    if subject_id:
        query = query.filter(AssetRelation.subject_id == subject_id)
    if relation_type:
        query = query.filter(AssetRelation.relation_type == relation_type)
        
    return query.all()


# ==========================================
# LLM 自动提取物品 Endpoints
# ==========================================

class ExtractPropsRequest(BaseModel):
    script_text: str
    chapter_id: Optional[str] = None


class ExtractPropsResponse(BaseModel):
    props_created: int
    outfits_created: int
    relations_created: int
    message: str


@router.post("/projects/{project_id}/extract-props", response_model=ExtractPropsResponse)
async def extract_props_from_script(
    project_id: str,
    request: ExtractPropsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    从剧本中自动提取物品和服装信息
    
    使用 LLM 分析剧本，自动创建：
    - PropAsset (手持物品、场景陈设)
    - OutfitVariant (服装变体)
    - AssetRelation (角色-物品关系)
    """
    from app.services.prop_extractor import PropExtractorService
    
    extractor = PropExtractorService(
        db=db,
        project_id=project_id,
        chapter_id=request.chapter_id
    )
    
    result = await extractor.extract_and_create_from_script(request.script_text)
    
    return ExtractPropsResponse(
        props_created=result["props_created"],
        outfits_created=result["outfits_created"],
        relations_created=result["relations_created"],
        message=f"成功提取 {result['props_created']} 个物品, {result['outfits_created']} 套服装"
    )
