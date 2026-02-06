"""
Prop Extractor Service - 物品/服装自动提取与创建服务
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.prop_asset import PropAsset, PropCategory
from app.models.outfit_variant import OutfitVariant
from app.models.asset_relation import AssetRelation, RelationType
from app.models.asset import Asset
from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)


class PropExtractorService:
    """
    物品/服装提取服务
    
    功能：
    1. 调用 LLM 从剧本中提取物品和服装信息
    2. 自动创建 PropAsset 和 OutfitVariant 记录
    3. 创建 AssetRelation 关联
    """
    
    def __init__(self, db: Session, project_id: str, chapter_id: Optional[str] = None):
        self.db = db
        self.project_id = project_id
        self.chapter_id = chapter_id
        self.llm = StandardLLMService()
    
    async def extract_and_create_from_script(self, script_text: str) -> Dict[str, Any]:
        """
        从剧本中提取物品和服装，并创建对应的数据库记录
        
        Returns:
            {
                "props_created": int,
                "outfits_created": int,
                "relations_created": int,
                "props": [...],
                "outfits": [...],
                "relations": [...]
            }
        """
        # Step 1: 调用 LLM 提取信息
        extraction = await self.llm.extract_props_and_outfits(script_text)
        
        # Step 2: 获取现有角色资产（用于关联服装）
        character_assets = self._get_character_assets()
        character_name_to_id = {a.name: a.id for a in character_assets}
        
        # Step 3: 创建 Props
        created_props = []
        for prop_data in extraction.get("hand_props", []):
            prop = self._create_prop(prop_data, PropCategory.HAND_PROP)
            if prop:
                created_props.append(prop)
        
        for prop_data in extraction.get("set_dressings", []):
            prop = self._create_prop(prop_data, PropCategory.SET_DRESSING)
            if prop:
                created_props.append(prop)
        
        # Step 4: 创建 Outfits
        created_outfits = []
        for outfit_data in extraction.get("outfits", []):
            outfit = self._create_outfit(outfit_data, character_name_to_id)
            if outfit:
                created_outfits.append(outfit)
        
        # Step 5: 创建 Relations
        created_relations = []
        prop_name_to_id = {p.canonical_name: p.id for p in created_props}
        
        for rel_data in extraction.get("character_prop_relations", []):
            relation = self._create_relation(rel_data, character_name_to_id, prop_name_to_id)
            if relation:
                created_relations.append(relation)
        
        # Commit all changes
        self.db.commit()
        
        logger.info(f"PropExtractor: Created {len(created_props)} props, "
                   f"{len(created_outfits)} outfits, {len(created_relations)} relations")
        
        return {
            "props_created": len(created_props),
            "outfits_created": len(created_outfits),
            "relations_created": len(created_relations),
            "props": [{"id": p.id, "name": p.canonical_name, "category": p.category} for p in created_props],
            "outfits": [{"id": o.id, "name": o.outfit_name} for o in created_outfits],
            "relations": [{"id": r.id, "type": r.relation_type} for r in created_relations],
            "raw_extraction": extraction
        }
    
    def _get_character_assets(self) -> List[Asset]:
        """获取项目中的角色资产"""
        return self.db.query(Asset).filter(
            Asset.project_id == self.project_id,
            Asset.type == "character",
            Asset.status == "active"
        ).all()
    
    def _create_prop(self, data: Dict[str, Any], category: str) -> Optional[PropAsset]:
        """创建单个 PropAsset"""
        canonical_name = data.get("canonical_name", "").strip()
        if not canonical_name:
            return None
        
        # 检查是否已存在
        existing = self.db.query(PropAsset).filter(
            PropAsset.project_id == self.project_id,
            PropAsset.canonical_name == canonical_name
        ).first()
        
        if existing:
            logger.debug(f"Prop '{canonical_name}' already exists, skipping")
            return existing
        
        prop = PropAsset(
            project_id=self.project_id,
            canonical_name=canonical_name,
            category=category,
            aliases=data.get("aliases", []),
            visual_brief=data.get("visual_brief"),
            material=data.get("material"),
            colors=data.get("colors", []),
            shape=data.get("shape"),
            key_features=data.get("key_features", []),
            status="pending"
        )
        self.db.add(prop)
        self.db.flush()  # Get the ID
        
        logger.debug(f"Created prop: {canonical_name} ({category})")
        return prop
    
    def _create_outfit(self, data: Dict[str, Any], char_name_to_id: Dict[str, str]) -> Optional[OutfitVariant]:
        """创建单个 OutfitVariant"""
        character_name = data.get("character_name", "").strip()
        outfit_name = data.get("outfit_name", "").strip()
        
        if not character_name or not outfit_name:
            return None
        
        # 查找角色 ID
        character_asset_id = char_name_to_id.get(character_name)
        if not character_asset_id:
            logger.warning(f"Character '{character_name}' not found for outfit '{outfit_name}'")
            return None
        
        # 检查是否已存在
        existing = self.db.query(OutfitVariant).filter(
            OutfitVariant.character_asset_id == character_asset_id,
            OutfitVariant.outfit_name == outfit_name
        ).first()
        
        if existing:
            logger.debug(f"Outfit '{outfit_name}' for {character_name} already exists, skipping")
            return existing
        
        # 生成 outfit_prompt
        outfit_prompt = self._generate_outfit_prompt(data)
        
        outfit = OutfitVariant(
            character_asset_id=character_asset_id,
            outfit_name=outfit_name,
            outfit_description=data.get("outfit_description", ""),
            garment_items=data.get("garment_items", []),
            colors=data.get("colors", []),
            materials=data.get("materials", []),
            outfit_prompt=outfit_prompt,
            is_default=data.get("is_default", False),
            status="pending"
        )
        self.db.add(outfit)
        self.db.flush()
        
        logger.debug(f"Created outfit: {outfit_name} for {character_name}")
        return outfit
    
    def _create_relation(
        self, 
        data: Dict[str, Any], 
        char_name_to_id: Dict[str, str],
        prop_name_to_id: Dict[str, str]
    ) -> Optional[AssetRelation]:
        """创建 AssetRelation"""
        character_name = data.get("character_name", "").strip()
        prop_name = data.get("prop_name", "").strip()
        relation_type = data.get("relation_type", "holds")
        
        character_id = char_name_to_id.get(character_name)
        prop_id = prop_name_to_id.get(prop_name)
        
        if not character_id or not prop_id:
            return None
        
        # 检查是否已存在
        existing = self.db.query(AssetRelation).filter(
            AssetRelation.project_id == self.project_id,
            AssetRelation.subject_id == character_id,
            AssetRelation.object_id == prop_id,
            AssetRelation.relation_type == relation_type
        ).first()
        
        if existing:
            return existing
        
        relation = AssetRelation(
            project_id=self.project_id,
            chapter_id=self.chapter_id,
            relation_type=relation_type,
            subject_id=character_id,
            subject_type="character",
            object_id=prop_id,
            object_type="prop",
            relation_metadata={"context": data.get("context", "")}
        )
        self.db.add(relation)
        self.db.flush()
        
        logger.debug(f"Created relation: {character_name} -{relation_type}-> {prop_name}")
        return relation
    
    def _generate_outfit_prompt(self, data: Dict[str, Any]) -> str:
        """生成服装提示词"""
        parts = []
        
        if data.get("outfit_description"):
            parts.append(data["outfit_description"])
        
        if data.get("garment_items"):
            parts.append(f"wearing {', '.join(data['garment_items'])}")
        
        if data.get("colors"):
            parts.append(f"in {', '.join(data['colors'])} colors")
        
        if data.get("materials"):
            parts.append(f"made of {', '.join(data['materials'])}")
        
        return ", ".join(parts) if parts else data.get("outfit_name", "")
