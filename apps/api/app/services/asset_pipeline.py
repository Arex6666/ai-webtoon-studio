"""
Asset Pipeline Orchestrator - 资产生成流水线编排器

协调完整的资产处理流程：
1. 从剧本分析提取资产
2. 名称解析与合并
3. 创建资产记录
4. 批量生成参考图
5. 提取 FaceID/控制图
"""
import logging
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.services.brain.name_resolver import NameResolver
from app.services.brain.asset_matcher import AssetMatcher
from app.services.brain.panel_attribute_filler import PanelAttributeFiller
from app.services.asset_image_generator import get_asset_image_generator
from app.schemas.script_ir import CharacterIR, SceneIR

logger = logging.getLogger(__name__)


class AssetPipelineOrchestrator:
    """资产生成流水线编排器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.name_resolver = NameResolver()
        self.asset_matcher = AssetMatcher()
        self.attribute_filler = PanelAttributeFiller()
        self.image_generator = get_asset_image_generator()
    
    async def process_script_analysis(
        self,
        project_id: str,
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理剧本分析结果，创建并生成资产
        
        Args:
            project_id: 项目ID
            analysis_data: ScriptAnalysisV1 数据
        
        Returns:
            {
                "created_assets": [...],
                "merged_characters": {...},
                "generation_jobs": [...]
            }
        """
        result = {
            "created_assets": [],
            "merged_characters": {},
            "generation_jobs": [],
            "errors": []
        }
        
        try:
            # 1. 提取并合并角色
            characters = analysis_data.get("characters", [])
            if characters:
                merged_chars = await self.name_resolver.merge_characters(characters)
                result["merged_characters"] = {
                    "original_count": len(characters),
                    "merged_count": len(merged_chars)
                }
                characters = merged_chars
            
            # 2. 创建角色资产
            for char in characters:
                asset = await self._create_character_asset(project_id, char)
                if asset:
                    result["created_assets"].append({
                        "id": asset.id,
                        "name": asset.name,
                        "type": "character",
                        "status": "pending"
                    })
            
            # 3. 提取并创建场景资产
            locations = analysis_data.get("locations", [])
            for loc in locations:
                asset = await self._create_scene_asset(project_id, loc)
                if asset:
                    result["created_assets"].append({
                        "id": asset.id,
                        "name": asset.name,
                        "type": "scene",
                        "status": "pending"
                    })
            
            # 4. 提取并创建物品资产
            props = analysis_data.get("props", [])
            for prop in props:
                asset = await self._create_prop_asset(project_id, prop)
                if asset:
                    result["created_assets"].append({
                        "id": asset.id,
                        "name": asset.name,
                        "type": "prop",
                        "status": "pending"
                    })
            
            self.db.commit()
            logger.info(f"Created {len(result['created_assets'])} assets for project {project_id}")
            
        except Exception as e:
            logger.error(f"Asset pipeline error: {e}")
            result["errors"].append(str(e))
        
        return result
    
    async def generate_assets_images(
        self,
        project_id: str,
        asset_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """为资产批量生成参考图
        
        Args:
            project_id: 项目ID
            asset_ids: 指定资产ID列表，为空则处理所有待生成资产
        
        Returns:
            生成任务结果
        """
        # 查询待处理资产
        query = self.db.query(Asset).filter(
            Asset.project_id == project_id,
            Asset.status.in_(["pending", "needs_image"])
        )
        
        if asset_ids:
            query = query.filter(Asset.id.in_(asset_ids))
        
        assets = query.all()
        
        results = []
        for asset in assets:
            try:
                if asset.asset_type == "character":
                    # 构建 CharacterIR
                    meta = asset.meta_json or {}
                    char_ir = CharacterIR(
                        name=asset.name,
                        gender=meta.get("gender"),
                        age_range=meta.get("age_range"),
                        appearance_keywords=meta.get("appearance_traits", []),
                    )
                    gen_result = await self.image_generator.generate_character_portrait(
                        character=char_ir,
                        asset=asset,
                        project_id=project_id
                    )
                    
                    # 更新资产状态
                    if gen_result.get("success"):
                        asset.reference_image = gen_result.get("image_url")
                        if gen_result.get("embedding_path"):
                            asset.status = "ready"
                            if not asset.meta_json:
                                asset.meta_json = {}
                            asset.meta_json["embedding_path"] = gen_result["embedding_path"]
                        else:
                            asset.status = "pending_faceid"
                    
                    results.append({
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "type": "character",
                        **gen_result
                    })
                    
                elif asset.asset_type == "scene":
                    # 构建 SceneIR
                    meta = asset.meta_json or {}
                    scene_ir = SceneIR(
                        name=asset.name,
                        location_type=meta.get("location_type"),
                        time_period=meta.get("time_of_day"),
                        weather=meta.get("weather"),
                        atmosphere_keywords=meta.get("atmosphere", []),
                        visual_description=meta.get("anchor_hint", ""),
                    )
                    gen_result = await self.image_generator.generate_scene_background(
                        scene=scene_ir,
                        asset=asset,
                        project_id=project_id
                    )
                    
                    if gen_result.get("success"):
                        asset.reference_image = gen_result.get("image_url")
                        if gen_result.get("control_maps"):
                            asset.status = "ready"
                            if not asset.meta_json:
                                asset.meta_json = {}
                            asset.meta_json["control_maps"] = gen_result["control_maps"]
                        else:
                            asset.status = "pending_anchor"
                    
                    results.append({
                        "asset_id": asset.id,
                        "asset_name": asset.name,
                        "type": "scene",
                        **gen_result
                    })
                    
            except Exception as e:
                logger.error(f"Failed to generate image for asset {asset.id}: {e}")
                results.append({
                    "asset_id": asset.id,
                    "asset_name": asset.name,
                    "type": asset.asset_type,
                    "success": False,
                    "error": str(e)
                })
        
        self.db.commit()
        
        return {
            "total": len(assets),
            "results": results,
            "succeeded": len([r for r in results if r.get("success")]),
            "failed": len([r for r in results if not r.get("success")])
        }
    
    async def auto_match_panel_assets(
        self,
        panel: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """自动匹配分镜中的资产引用并填充属性
        
        Args:
            panel: 分镜数据
            project_id: 项目ID
        
        Returns:
            匹配结果和填充后的属性
        """
        # 获取项目资产
        assets = self.db.query(Asset).filter(
            Asset.project_id == project_id
        ).all()
        
        # 匹配资产
        match_result = await self.asset_matcher.auto_match_panel(panel, assets)
        
        # 填充属性
        filled_panel = await self.attribute_filler.fill_attributes(panel)
        
        return {
            "asset_matches": match_result,
            "filled_attributes": {
                "shot_type": filled_panel.get("shot_type"),
                "camera_move": filled_panel.get("camera_move"),
                "duration_s": filled_panel.get("duration_s"),
                "mood": filled_panel.get("mood"),
                "time_of_day": filled_panel.get("time_of_day"),
                "weather": filled_panel.get("weather"),
                "motion_description": filled_panel.get("motion_description"),
            }
        }
    
    async def _create_character_asset(
        self,
        project_id: str,
        char_data: Dict
    ) -> Optional[Asset]:
        """创建角色资产"""
        name = char_data.get("canonical_name", "").strip()
        if not name or len(name) < 2:
            return None
        
        # 检查是否已存在
        existing = self.db.query(Asset).filter(
            Asset.project_id == project_id,
            Asset.name == name,
            Asset.asset_type == "character"
        ).first()
        
        if existing:
            return existing
        
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            asset_type="character",
            name=name,
            status="pending",
            meta_json={
                "appearance_traits": char_data.get("appearance_traits", []),
                "personality_traits": char_data.get("personality_traits", []),
                "gender": char_data.get("gender"),
                "age_range": char_data.get("age_range"),
                "aliases": char_data.get("aliases", []),
            }
        )
        self.db.add(asset)
        return asset
    
    async def _create_scene_asset(
        self,
        project_id: str,
        loc_data: Dict
    ) -> Optional[Asset]:
        """创建场景资产"""
        name = loc_data.get("canonical_location", "").strip()
        if not name:
            return None
        
        # 检查是否已存在
        existing = self.db.query(Asset).filter(
            Asset.project_id == project_id,
            Asset.name == name,
            Asset.asset_type == "scene"
        ).first()
        
        if existing:
            return existing
        
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            asset_type="scene",
            name=name,
            status="pending",
            meta_json={
                "anchor_hint": loc_data.get("anchor_hint", ""),
                "is_primary": loc_data.get("is_primary", False),
            }
        )
        self.db.add(asset)
        return asset
    
    async def _create_prop_asset(
        self,
        project_id: str,
        prop_data: Dict
    ) -> Optional[Asset]:
        """创建物品资产"""
        name = prop_data.get("canonical_name", "").strip()
        if not name:
            return None
        
        # 检查是否已存在
        existing = self.db.query(Asset).filter(
            Asset.project_id == project_id,
            Asset.name == name,
            Asset.asset_type == "prop"
        ).first()
        
        if existing:
            return existing
        
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            asset_type="prop",
            name=name,
            status="pending",
            meta_json={
                "description": prop_data.get("description", ""),
                "owner": prop_data.get("owner"),
                "significance": prop_data.get("significance", "medium"),
            }
        )
        self.db.add(asset)
        return asset


def get_asset_pipeline(db: Session) -> AssetPipelineOrchestrator:
    """获取资产流水线实例"""
    return AssetPipelineOrchestrator(db)
