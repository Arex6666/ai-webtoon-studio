"""
Prop Asset Schemas
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.models.prop_asset import PropCategory


# ============ Prop Asset ============

class PropAssetBase(BaseModel):
    project_id: str
    canonical_name: str
    category: str = PropCategory.HAND_PROP
    
    # 视觉描述
    visual_brief: Optional[str] = None
    material: Optional[str] = None
    colors: List[str] = []
    shape: Optional[str] = None
    key_features: List[str] = []
    
    # 别名
    aliases: List[str] = []


class PropAssetCreate(PropAssetBase):
    pass


class PropAssetUpdate(BaseModel):
    canonical_name: Optional[str] = None
    category: Optional[str] = None
    visual_brief: Optional[str] = None
    material: Optional[str] = None
    colors: Optional[List[str]] = None
    shape: Optional[str] = None
    key_features: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    status: Optional[str] = None


class PropAssetResponse(PropAssetBase):
    id: str
    status: str
    default_prompt_tokens: List[str]
    ref_image_paths: List[str]
    ref_image_status: str
    embedding_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Outfit Variant ============

class OutfitVariantBase(BaseModel):
    character_asset_id: str
    outfit_name: str
    outfit_description: str
    garment_items: List[str] = []
    colors: List[str] = []
    materials: List[str] = []
    outfit_prompt: str
    is_default: bool = False


class OutfitVariantCreate(OutfitVariantBase):
    pass


class OutfitVariantUpdate(BaseModel):
    outfit_name: Optional[str] = None
    outfit_description: Optional[str] = None
    garment_items: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    materials: Optional[List[str]] = None
    outfit_prompt: Optional[str] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class OutfitVariantResponse(OutfitVariantBase):
    id: str
    ref_image_path: Optional[str]
    ref_image_status: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Asset Relation ============

class AssetRelationBase(BaseModel):
    project_id: str
    chapter_id: Optional[str] = None
    relation_type: str
    subject_id: str
    subject_type: str
    object_id: str
    object_type: str
    metadata: Dict[str, Any] = {}  # Used for input/output, mapped to relation_metadata in DB


class AssetRelationCreate(AssetRelationBase):
    pass


class AssetRelationResponse(BaseModel):
    id: str
    project_id: str
    chapter_id: Optional[str] = None
    relation_type: str
    subject_id: str
    subject_type: str
    object_id: str
    object_type: str
    relation_metadata: Dict[str, Any] = {}  # Maps to DB field
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

