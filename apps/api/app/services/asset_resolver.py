"""
Asset Resolver Service (S3-03)

将 AI 输出的角色/场景名称解析为实际的 Asset ID。
支持精确匹配、模糊匹配，以及创建 AssetDraft（待用户确认）。
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.asset import Asset


@dataclass
class ResolveResult:
    """匹配结果"""
    matched: bool
    asset_id: Optional[str] = None
    asset_name: Optional[str] = None
    confidence: float = 0.0
    # 如果未匹配，提供建议
    suggested_name: Optional[str] = None
    similar_assets: List[Dict] = None

    def __post_init__(self):
        if self.similar_assets is None:
            self.similar_assets = []


class AssetResolver:
    """
    资产解析器：将 AI 输出的文本引用转为 Asset ID
    
    匹配策略：
    1. 精确匹配 (名称相同)
    2. 模糊匹配 (相似度 > 阈值)
    3. 未匹配 -> 返回未匹配结果，可创建 AssetDraft
    """
    
    def __init__(self, db: Session, project_id: str):
        self.db = db
        self.project_id = project_id
        self._character_cache: Dict[str, Asset] = {}
        self._scene_cache: Dict[str, Asset] = {}
        self._load_assets()
    
    def _load_assets(self):
        """预加载项目资产到缓存"""
        assets = self.db.query(Asset).filter(
            Asset.project_id == self.project_id
        ).all()
        
        for asset in assets:
            if asset.type == "character":
                self._character_cache[asset.name.lower()] = asset
            elif asset.type == "scene":
                self._scene_cache[asset.name.lower()] = asset
    
    def resolve_character(self, name: str) -> ResolveResult:
        """
        解析角色名称
        
        Args:
            name: AI 输出的角色名称
            
        Returns:
            ResolveResult 包含匹配结果
        """
        if not name:
            return ResolveResult(matched=False, suggested_name=name)
        
        name_lower = name.lower().strip()
        
        # 1. 精确匹配
        if name_lower in self._character_cache:
            asset = self._character_cache[name_lower]
            return ResolveResult(
                matched=True,
                asset_id=asset.id,
                asset_name=asset.name,
                confidence=1.0
            )
        
        # 2. 模糊匹配 (简单版：包含关系)
        similar = []
        for cached_name, asset in self._character_cache.items():
            # 检查是否为子串
            if name_lower in cached_name or cached_name in name_lower:
                similar.append({
                    "id": asset.id,
                    "name": asset.name,
                    "confidence": 0.8
                })
            # 检查首字符匹配 (用于"小明" vs "明明"这类情况)
            elif name_lower[0] == cached_name[0] and len(name_lower) <= 3:
                similar.append({
                    "id": asset.id,
                    "name": asset.name,
                    "confidence": 0.5
                })
        
        if similar:
            # 返回置信度最高的
            similar.sort(key=lambda x: x["confidence"], reverse=True)
            best = similar[0]
            if best["confidence"] >= 0.7:
                return ResolveResult(
                    matched=True,
                    asset_id=best["id"],
                    asset_name=best["name"],
                    confidence=best["confidence"],
                    similar_assets=similar
                )
            else:
                return ResolveResult(
                    matched=False,
                    suggested_name=name,
                    similar_assets=similar
                )
        
        # 3. 未匹配
        return ResolveResult(
            matched=False,
            suggested_name=name
        )
    
    def resolve_scene(self, name: str) -> ResolveResult:
        """
        解析场景名称
        
        Args:
            name: AI 输出的场景名称/描述
            
        Returns:
            ResolveResult 包含匹配结果
        """
        if not name:
            return ResolveResult(matched=False, suggested_name=name)
        
        name_lower = name.lower().strip()
        
        # 1. 精确匹配
        if name_lower in self._scene_cache:
            asset = self._scene_cache[name_lower]
            return ResolveResult(
                matched=True,
                asset_id=asset.id,
                asset_name=asset.name,
                confidence=1.0
            )
        
        # 2. 模糊匹配
        similar = []
        for cached_name, asset in self._scene_cache.items():
            if name_lower in cached_name or cached_name in name_lower:
                similar.append({
                    "id": asset.id,
                    "name": asset.name,
                    "confidence": 0.8
                })
        
        if similar:
            similar.sort(key=lambda x: x["confidence"], reverse=True)
            best = similar[0]
            if best["confidence"] >= 0.7:
                return ResolveResult(
                    matched=True,
                    asset_id=best["id"],
                    asset_name=best["name"],
                    confidence=best["confidence"],
                    similar_assets=similar
                )
            else:
                return ResolveResult(
                    matched=False,
                    suggested_name=name,
                    similar_assets=similar
                )
        
        # 3. 未匹配
        return ResolveResult(
            matched=False,
            suggested_name=name
        )
    
    def resolve_all(
        self, 
        character_names: List[str], 
        scene_names: List[str]
    ) -> Dict:
        """
        批量解析角色和场景
        
        Returns:
            {
                "characters": [ResolveResult, ...],
                "scenes": [ResolveResult, ...],
                "unmatched_count": int,
                "matched_count": int
            }
        """
        char_results = [self.resolve_character(name) for name in character_names]
        scene_results = [self.resolve_scene(name) for name in scene_names]
        
        matched = sum(1 for r in char_results + scene_results if r.matched)
        unmatched = len(char_results) + len(scene_results) - matched
        
        return {
            "characters": char_results,
            "scenes": scene_results,
            "matched_count": matched,
            "unmatched_count": unmatched
        }


def get_asset_resolver(db: Session, project_id: str) -> AssetResolver:
    """获取 AssetResolver 实例"""
    return AssetResolver(db, project_id)
