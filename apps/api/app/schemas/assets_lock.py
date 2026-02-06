"""
Assets Lock Schema (S3-03)

记录章节已锁定的资产绑定，确保渲染/导出时的一致性。
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class FaceEmbeddingStatus(BaseModel):
    """FaceID Embedding 状态"""
    status: str = "missing"  # ready / missing / failed
    embedding_id: Optional[str] = None
    embedding_path: Optional[str] = None
    det_score: Optional[float] = None
    error_message: Optional[str] = None


class CharacterLock(BaseModel):
    """角色资产锁定信息 (P0-CH-06 增强版)"""
    asset_id: Optional[str] = None  # None for pending assets
    name: str
    role_name: Optional[str] = None  # 剧本角色名
    character_id: Optional[str] = None  # 稳定角色 ID (ch_xxx)
    
    # 绑定状态
    binding_status: str = "pending"  # exact / fuzzy / pending
    match_confidence: float = 0.0
    matched_by: Optional[str] = None  # name / alias / manual / embedding
    
    # FaceID Embedding 状态 (P0-CH-05/06)
    face_embedding_required: bool = True
    face_embedding: FaceEmbeddingStatus = Field(default_factory=FaceEmbeddingStatus)
    
    # Canonical Portrait 状态 (P0-CH-04)
    canonical_status: str = "pending"  # pending / running / succeeded / failed
    canonical_selected_path: Optional[str] = None
    canonical_selected_score: Optional[float] = None
    canonical_selection_reason: Optional[str] = None
    canonical_candidates_count: int = 0
    
    # 原有字段
    face_embedding_path: Optional[str] = None
    lora_path: Optional[str] = None
    ip_adapter_ref: Optional[str] = None
    reference_images: List[str] = Field(default_factory=list)
    consistency_weight: float = 0.8
    
    # S5-01: 参考图生成状态
    reference_image_status: str = "none"  # none|generating|ready|failed
    reference_image_path: Optional[str] = None  # 主参考图 URL
    
    @property
    def is_render_ready(self) -> bool:
        """是否可以渲染"""
        if self.binding_status != "exact":
            return False
        if self.face_embedding_required and self.face_embedding.status != "ready":
            return False
        return True



class SceneLock(BaseModel):
    """场景资产锁定信息"""
    asset_id: Optional[str] = None  # None for pending assets
    name: str
    anchor_image_path: Optional[str] = None
    depth_map_path: Optional[str] = None
    style_preset: Optional[str] = None
    reference_images: List[str] = Field(default_factory=list)
    
    # S5-SC: 锚点生成状态
    anchor_status: str = "none"  # none|generating|ready|failed
    control_map_status: str = "none"  # none|generating|ready|failed
    control_maps: Dict[str, str] = Field(default_factory=dict)  # {depth, lineart, canny}
    
    @property
    def is_render_ready(self) -> bool:
        """场景是否可渲染"""
        return self.anchor_status == "ready"


class StyleLock(BaseModel):
    """风格资产锁定信息"""
    asset_id: Optional[str] = None  # None for pending assets
    name: str
    lora_path: Optional[str] = None
    checkpoint_hint: Optional[str] = None
    sampler_preset: Optional[Dict] = None


class AssetsLock(BaseModel):
    """
    章节资产锁定文件
    
    用于渲染/导出时确保一致性：
    - 锁定角色的 FaceID/LoRA 路径
    - 锁定场景的锚点图/深度图
    - 锁定风格的 LoRA/Checkpoint
    """
    version: int = 1
    locked_at: datetime = Field(default_factory=datetime.utcnow)
    chapter_id: str
    project_id: str
    
    # 锁定的资产
    characters: Dict[str, CharacterLock] = Field(default_factory=dict)  # asset_id -> lock
    scenes: Dict[str, SceneLock] = Field(default_factory=dict)
    styles: Dict[str, StyleLock] = Field(default_factory=dict)
    
    # 元信息
    storyboard_version: int = 1
    generated_from_draft_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_character(self, asset_id: str, lock: CharacterLock):
        """添加角色锁定"""
        self.characters[asset_id] = lock
    
    def add_scene(self, asset_id: str, lock: SceneLock):
        """添加场景锁定"""
        self.scenes[asset_id] = lock
    
    def add_style(self, asset_id: str, lock: StyleLock):
        """添加风格锁定"""
        self.styles[asset_id] = lock
    
    def get_character_paths(self, asset_id: str) -> Dict[str, Optional[str]]:
        """获取角色的一致性路径"""
        lock = self.characters.get(asset_id)
        if not lock:
            return {}
        return {
            "face_embedding": lock.face_embedding_path,
            "lora": lock.lora_path,
            "ip_adapter": lock.ip_adapter_ref,
            "references": lock.reference_images
        }
    
    def get_scene_paths(self, asset_id: str) -> Dict[str, Optional[str]]:
        """获取场景的一致性路径"""
        lock = self.scenes.get(asset_id)
        if not lock:
            return {}
        return {
            "anchor": lock.anchor_image_path,
            "depth": lock.depth_map_path,
            "references": lock.reference_images
        }
    
    def to_render_context(self) -> Dict:
        """转换为渲染上下文"""
        return {
            "characters": {
                asset_id: {
                    "name": lock.name,
                    "face_embedding": lock.face_embedding_path,
                    "lora": lock.lora_path,
                    "ip_adapter": lock.ip_adapter_ref,
                    "weight": lock.consistency_weight
                }
                for asset_id, lock in self.characters.items()
            },
            "scenes": {
                asset_id: {
                    "name": lock.name,
                    "anchor": lock.anchor_image_path,
                    "depth": lock.depth_map_path,
                    "style": lock.style_preset
                }
                for asset_id, lock in self.scenes.items()
            },
            "styles": {
                asset_id: {
                    "name": lock.name,
                    "lora": lock.lora_path,
                    "checkpoint": lock.checkpoint_hint
                }
                for asset_id, lock in self.styles.items()
            }
        }


def create_assets_lock(
    chapter_id: str,
    project_id: str,
    draft_id: Optional[str] = None
) -> AssetsLock:
    """创建新的资产锁定文件"""
    return AssetsLock(
        chapter_id=chapter_id,
        project_id=project_id,
        generated_from_draft_id=draft_id
    )
