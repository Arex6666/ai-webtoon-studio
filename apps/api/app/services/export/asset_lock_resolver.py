"""
Asset Lock Resolver - 资产锁定解析器

负责收集章节内所有引用资产的版本信息，生成 assets.json
"""
import logging
from typing import List, Dict, Set, Optional
from sqlalchemy.orm import Session

from app.models import Panel, LayerPack, Asset, AssetVersion
from app.schemas.bundle_manifest import AssetsLockSpec, AssetsLockEntry
from app.services.export.bundle_models import ChapterSnapshot, PanelArtifactPlan

logger = logging.getLogger(__name__)


class AssetLockResolver:
    """资产锁定解析器"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # 缓存
        self._assets_cache: Dict[str, Asset] = {}
        self._versions_cache: Dict[str, AssetVersion] = {}
        
        # 收集器
        self.models: Dict[str, AssetsLockEntry] = {}
        self.loras: Dict[str, AssetsLockEntry] = {}
        self.embeddings: Dict[str, AssetsLockEntry] = {}
        self.face_embeddings: Dict[str, AssetsLockEntry] = {}
        self.scene_anchors: Dict[str, AssetsLockEntry] = {}
        self.fonts: Dict[str, AssetsLockEntry] = {}
    
    def resolve(
        self, 
        chapter_snapshot: ChapterSnapshot, 
        panel_plans: List[PanelArtifactPlan]
    ) -> AssetsLockSpec:
        """
        解析整个章节的资产依赖
        """
        logger.info(f"Resolving assets for chapter {chapter_snapshot.chapter_id}")
        
        for plan in panel_plans:
            if not plan.layerpack_id:
                continue
                
            layerpack = self.db.query(LayerPack).filter(LayerPack.id == plan.layerpack_id).first()
            if layerpack:
                self._collect_from_layerpack(layerpack)
        
        # 转换为 Spec
        return AssetsLockSpec(
            spec_version="1.0.0",
            chapter_id=chapter_snapshot.chapter_id,
            exported_at=chapter_snapshot.exported_at if hasattr(chapter_snapshot, 'exported_at') else "",
            models=list(self.models.values()),
            loras=list(self.loras.values()),
            embeddings=list(self.embeddings.values()),
            face_embeddings=list(self.face_embeddings.values()),
            scene_anchors=list(self.scene_anchors.values()),
            fonts=list(self.fonts.values()),
            total_assets=(
                len(self.models) + len(self.loras) + len(self.embeddings) +
                len(self.face_embeddings) + len(self.scene_anchors) + len(self.fonts)
            )
        )
    
    def _collect_from_layerpack(self, layerpack: LayerPack):
        """从 LayerPack 收集资产引用"""
        # 1. 模型依赖 (从 provenance)
        params = layerpack.params_json or {}
        gen_params = layerpack.generation_params or {}
        
        # Checkpoint
        model_name = gen_params.get("model_name") or params.get("model")
        if model_name:
            self._add_model("checkpoint", model_name)
            
        # LoRAs
        loras = gen_params.get("loras", []) or params.get("loras", [])
        for lora in loras:
            name = lora.get("name") if isinstance(lora, dict) else lora
            if name:
                self._add_model("lora", name)
                
        # 2. 也是从 inputs 收集 (face/scene)
        # TODO: 从 LayerPackInputs 收集 (目前 LayerPack 表结构还不完全支持 structured inputs)
        
        # 临时：尝试从 params 解析 face/scene
        if "face_id" in params:
            self._add_face_embedding(params["face_id"])
            
        if "scene_id" in params:
            self._add_scene_anchor(params["scene_id"])
            
    def _add_model(self, type: str, name: str):
        """添加模型引用"""
        key = f"{type}:{name}"
        
        # 如果是已知资产库的模型
        # asset = self._find_asset_by_name(name, type)
        # ...
        
        entry = AssetsLockEntry(
            asset_type=type,
            asset_id=f"ext-{type}-{hash(name)}",  # 临时 ID
            name=name,
            version_id=None,
            hash=None
        )
        
        if type == "checkpoint":
            self.models[key] = entry
        elif type == "lora":
            self.loras[key] = entry
        elif type == "embedding":
            self.embeddings[key] = entry
            
    def _add_face_embedding(self, face_id: str):
        """添加人脸向量引用"""
        if face_id in self.face_embeddings:
            return
            
        entry = AssetsLockEntry(
            asset_type="face_embedding",
            asset_id=face_id,
            name=f"Face {face_id}",
            version_id="v1" 
        )
        self.face_embeddings[face_id] = entry
        
    def _add_scene_anchor(self, scene_id: str):
        """添加场景锚点引用"""
        if scene_id in self.scene_anchors:
            return
            
        entry = AssetsLockEntry(
            asset_type="scene_anchor",
            asset_id=scene_id,
            name=f"Scene {scene_id}"
        )
        self.scene_anchors[scene_id] = entry
