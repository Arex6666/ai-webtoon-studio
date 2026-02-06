"""
AssetMatcher - 智能资产匹配器
使用名称匹配、标签匹配和LLM语义匹配来自动关联资产
"""
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class MatchConfidence(str, Enum):
    """匹配置信度级别"""
    HIGH = "high"           # >0.9 自动匹配
    MEDIUM = "medium"       # 0.7-0.9 建议匹配，需确认
    LOW = "low"             # 0.4-0.7 候选项
    NONE = "none"           # <0.4 无匹配


class AssetType(str, Enum):
    """资产类型"""
    CHARACTER = "character"
    SCENE = "scene"
    PROP = "prop"


class AssetCandidate(BaseModel):
    """资产匹配候选"""
    asset_id: str = Field(..., description="资产ID")
    name: str = Field(..., description="资产名称")
    asset_type: AssetType = Field(..., description="资产类型")
    score: float = Field(..., description="匹配分数 0-1")
    confidence: MatchConfidence = Field(..., description="置信度级别")
    match_reason: str = Field("", description="匹配原因")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    tags: List[str] = Field(default_factory=list, description="资产标签")


class MatchRequest(BaseModel):
    """匹配请求"""
    query: str = Field(..., description="查询词（名称或描述）")
    asset_type: AssetType = Field(..., description="资产类型")
    context: Optional[str] = Field(None, description="上下文描述")
    project_id: Optional[str] = Field(None, description="项目ID")


class MatchResult(BaseModel):
    """匹配结果"""
    query: str = Field(..., description="原始查询")
    asset_type: AssetType = Field(..., description="资产类型")
    best_match: Optional[AssetCandidate] = Field(None, description="最佳匹配")
    candidates: List[AssetCandidate] = Field(default_factory=list, description="候选列表")
    needs_confirmation: bool = Field(False, description="是否需要用户确认")
    needs_generation: bool = Field(False, description="是否需要生成新资产")


class AssetMatcher:
    """
    智能资产匹配器
    
    匹配策略:
    1. 精确名称匹配 (score=1.0)
    2. 模糊名称匹配 (SequenceMatcher)
    3. 标签匹配
    4. LLM语义匹配 (可选)
    """

    def __init__(
        self,
        auto_match_threshold: float = 0.9,
        confirm_threshold: float = 0.7,
        candidate_threshold: float = 0.4,
    ):
        """
        初始化匹配器
        
        Args:
            auto_match_threshold: 自动匹配阈值
            confirm_threshold: 需确认匹配阈值
            candidate_threshold: 候选项阈值
        """
        self.auto_match_threshold = auto_match_threshold
        self.confirm_threshold = confirm_threshold
        self.candidate_threshold = candidate_threshold
        
        # 内存资产库（生产环境需替换为数据库查询）
        self._assets: Dict[str, Dict[str, Any]] = {}

    def register_asset(
        self,
        asset_id: str,
        name: str,
        asset_type: AssetType,
        tags: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        description: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """注册资产到匹配器"""
        self._assets[asset_id] = {
            "id": asset_id,
            "name": name,
            "type": asset_type,
            "tags": tags or [],
            "aliases": aliases or [],
            "description": description or "",
            "thumbnail_url": thumbnail_url,
            "project_id": project_id,
        }

    def match(self, request: MatchRequest) -> MatchResult:
        """
        执行资产匹配
        
        Args:
            request: 匹配请求
            
        Returns:
            匹配结果
        """
        candidates = []
        query_lower = request.query.lower().strip()
        
        for asset_id, asset in self._assets.items():
            # 过滤类型
            if asset["type"] != request.asset_type:
                continue
            
            # 过滤项目（如果指定）
            if request.project_id and asset.get("project_id"):
                if asset["project_id"] != request.project_id:
                    continue
            
            # 计算匹配分数
            score, reason = self._calculate_match_score(query_lower, asset, request.context)
            
            if score >= self.candidate_threshold:
                confidence = self._get_confidence_level(score)
                candidates.append(AssetCandidate(
                    asset_id=asset_id,
                    name=asset["name"],
                    asset_type=asset["type"],
                    score=score,
                    confidence=confidence,
                    match_reason=reason,
                    thumbnail_url=asset.get("thumbnail_url"),
                    tags=asset.get("tags", []),
                ))
        
        # 按分数排序
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        # 确定最佳匹配和状态
        best_match = candidates[0] if candidates else None
        needs_confirmation = False
        needs_generation = False
        
        if best_match:
            if best_match.score >= self.auto_match_threshold:
                # 高置信度，自动匹配
                needs_confirmation = False
            elif best_match.score >= self.confirm_threshold:
                # 中等置信度，需确认
                needs_confirmation = True
            else:
                # 低置信度，需确认或生成
                needs_confirmation = True
                needs_generation = True
        else:
            # 无匹配，需要生成
            needs_generation = True
        
        return MatchResult(
            query=request.query,
            asset_type=request.asset_type,
            best_match=best_match,
            candidates=candidates[:5],  # 最多返回5个候选
            needs_confirmation=needs_confirmation,
            needs_generation=needs_generation,
        )

    def _calculate_match_score(
        self,
        query: str,
        asset: Dict[str, Any],
        context: Optional[str],
    ) -> tuple[float, str]:
        """计算匹配分数"""
        max_score = 0.0
        reason = ""
        
        name_lower = asset["name"].lower()
        
        # 1. 精确匹配
        if query == name_lower:
            return 1.0, "精确名称匹配"
        
        # 2. 别名精确匹配
        for alias in asset.get("aliases", []):
            if query == alias.lower():
                return 0.98, f"别名匹配: {alias}"
        
        # 3. 模糊名称匹配
        name_similarity = SequenceMatcher(None, query, name_lower).ratio()
        if name_similarity > max_score:
            max_score = name_similarity
            reason = f"名称相似度: {name_similarity:.0%}"
        
        # 4. 包含关系匹配
        if query in name_lower:
            contain_score = 0.85
            if contain_score > max_score:
                max_score = contain_score
                reason = f"名称包含关系"
        elif name_lower in query:
            contain_score = 0.75
            if contain_score > max_score:
                max_score = contain_score
                reason = f"查询包含名称"
        
        # 5. 标签匹配
        for tag in asset.get("tags", []):
            tag_lower = tag.lower()
            if query == tag_lower:
                tag_score = 0.8
                if tag_score > max_score:
                    max_score = tag_score
                    reason = f"标签匹配: {tag}"
            elif query in tag_lower or tag_lower in query:
                tag_score = 0.6
                if tag_score > max_score:
                    max_score = tag_score
                    reason = f"标签相关: {tag}"
        
        # 6. 描述匹配
        description = asset.get("description", "").lower()
        if description and query in description:
            desc_score = 0.5
            if desc_score > max_score:
                max_score = desc_score
                reason = "描述中包含查询词"
        
        return max_score, reason

    def _get_confidence_level(self, score: float) -> MatchConfidence:
        """根据分数获取置信度级别"""
        if score >= self.auto_match_threshold:
            return MatchConfidence.HIGH
        elif score >= self.confirm_threshold:
            return MatchConfidence.MEDIUM
        elif score >= self.candidate_threshold:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.NONE

    def batch_match(
        self,
        queries: List[Dict[str, Any]],
    ) -> Dict[str, MatchResult]:
        """
        批量匹配
        
        Args:
            queries: 查询列表 [{"query": "角色名", "type": "character"}, ...]
            
        Returns:
            {query: MatchResult}
        """
        results = {}
        for q in queries:
            request = MatchRequest(
                query=q["query"],
                asset_type=AssetType(q["type"]),
                context=q.get("context"),
                project_id=q.get("project_id"),
            )
            results[q["query"]] = self.match(request)
        return results

    def extract_and_match(
        self,
        storyboard: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从分镜中提取资产需求并匹配
        
        Args:
            storyboard: 分镜数据
            project_id: 项目ID
            
        Returns:
            匹配结果汇总
        """
        # 提取角色
        character_names = set()
        for char in storyboard.get("characters", []):
            if isinstance(char, dict):
                character_names.add(char.get("name", ""))
            else:
                character_names.add(str(char))
        
        for panel in storyboard.get("panels", []):
            for char in panel.get("characters", []):
                character_names.add(str(char))
        
        # 提取场景
        scene_names = set()
        for scene in storyboard.get("scenes", []):
            if isinstance(scene, dict):
                scene_names.add(scene.get("name", ""))
            else:
                scene_names.add(str(scene))
        
        for panel in storyboard.get("panels", []):
            if panel.get("scene"):
                scene_names.add(str(panel["scene"]))
        
        # 提取道具
        prop_names = set()
        for panel in storyboard.get("panels", []):
            for prop in panel.get("props", []):
                if isinstance(prop, dict):
                    prop_names.add(prop.get("name", ""))
                else:
                    prop_names.add(str(prop))
        
        # 批量匹配
        queries = []
        for name in character_names:
            if name:
                queries.append({"query": name, "type": "character", "project_id": project_id})
        for name in scene_names:
            if name:
                queries.append({"query": name, "type": "scene", "project_id": project_id})
        for name in prop_names:
            if name:
                queries.append({"query": name, "type": "prop", "project_id": project_id})
        
        results = self.batch_match(queries)
        
        # 汇总统计
        auto_matched = sum(1 for r in results.values() if r.best_match and not r.needs_confirmation)
        needs_confirm = sum(1 for r in results.values() if r.needs_confirmation and not r.needs_generation)
        needs_gen = sum(1 for r in results.values() if r.needs_generation)
        
        return {
            "results": {k: v.dict() for k, v in results.items()},
            "summary": {
                "total": len(results),
                "auto_matched": auto_matched,
                "needs_confirmation": needs_confirm,
                "needs_generation": needs_gen,
            }
        }

    def get_registered_assets(
        self,
        asset_type: Optional[AssetType] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取已注册的资产列表"""
        assets = []
        for asset in self._assets.values():
            if asset_type and asset["type"] != asset_type:
                continue
            if project_id and asset.get("project_id") != project_id:
                continue
            assets.append(asset)
        return assets
