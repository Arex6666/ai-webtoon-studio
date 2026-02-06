"""
SceneMatcher - 场景智能匹配服务

实现三层匹配策略：
1. 精确匹配：name == query
2. 别名匹配：query in aliases
3. 语义匹配：LLM 判断语义相似性

支持场景变体（天气/时间）
"""
import logging
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from app.services.brain.standard_llm import StandardLLMService
from app.models.asset import Asset
import json

logger = logging.getLogger(__name__)


@dataclass
class SceneVariant:
    """场景变体"""
    condition: str  # e.g., "night", "rain", "night_rain"
    prompt_modifier: str  # e.g., "night time, dark atmosphere..."
    reference_image: Optional[str] = None


@dataclass
class SceneMatchResult:
    """场景匹配结果"""
    scene_id: Optional[str]
    scene_name: str
    match_type: str  # "exact", "alias", "semantic", "none"
    confidence: float
    variant: Optional[SceneVariant] = None
    visual_prompt: Optional[str] = None


class SceneMatcher:
    """场景智能匹配器"""
    
    def __init__(self, llm_service: Optional[StandardLLMService] = None):
        self.llm = llm_service or StandardLLMService()
    
    async def match(
        self,
        description: str,
        project_assets: List[Asset],
        time_of_day: Optional[str] = None,
        weather: Optional[str] = None,
    ) -> SceneMatchResult:
        """匹配场景描述到资产库中的场景
        
        Args:
            description: 分镜中的地点描述
            project_assets: 项目中的所有资产
            time_of_day: 时间 (day/night/dawn/dusk)
            weather: 天气 (clear/rain/snow/cloudy)
        
        Returns:
            SceneMatchResult
        """
        if not description:
            return SceneMatchResult(
                scene_id=None,
                scene_name=description,
                match_type="none",
                confidence=0.0
            )
        
        # 筛选场景类型资产
        scene_assets = [a for a in project_assets if a.type == "scene"]
        
        if not scene_assets:
            return SceneMatchResult(
                scene_id=None,
                scene_name=description,
                match_type="none",
                confidence=0.0
            )
        
        # 第1层：精确匹配
        for asset in scene_assets:
            if asset.name == description:
                result = self._build_result(asset, "exact", 1.0, time_of_day, weather)
                logger.info(f"SceneMatcher: exact match '{description}' -> {asset.name}")
                return result
        
        # 第2层：别名匹配
        for asset in scene_assets:
            aliases = self._get_aliases(asset)
            if description in aliases:
                result = self._build_result(asset, "alias", 0.9, time_of_day, weather)
                logger.info(f"SceneMatcher: alias match '{description}' -> {asset.name}")
                return result
            
            # 模糊别名匹配（包含关系）
            for alias in aliases:
                if alias in description or description in alias:
                    result = self._build_result(asset, "alias", 0.8, time_of_day, weather)
                    logger.info(f"SceneMatcher: fuzzy alias match '{description}' -> {asset.name}")
                    return result
        
        # 包含匹配
        for asset in scene_assets:
            if asset.name in description or description in asset.name:
                result = self._build_result(asset, "alias", 0.7, time_of_day, weather)
                logger.info(f"SceneMatcher: contains match '{description}' -> {asset.name}")
                return result
        
        # 第3层：语义匹配（LLM）
        semantic_result = await self._semantic_match(description, scene_assets)
        if semantic_result:
            asset, confidence = semantic_result
            result = self._build_result(asset, "semantic", confidence, time_of_day, weather)
            logger.info(f"SceneMatcher: semantic match '{description}' -> {asset.name} (confidence={confidence})")
            return result
        
        # 无匹配
        return SceneMatchResult(
            scene_id=None,
            scene_name=description,
            match_type="none",
            confidence=0.0
        )
    
    def _get_aliases(self, asset: Asset) -> List[str]:
        """获取资产的别名列表"""
        data = asset.data_json or {}
        return data.get("aliases", [])
    
    def _get_visual_prompt(self, asset: Asset) -> Optional[str]:
        """获取资产的视觉提示词"""
        data = asset.data_json or {}
        return data.get("visual_prompt")
    
    def _get_variants(self, asset: Asset) -> List[Dict[str, Any]]:
        """获取资产的变体列表"""
        data = asset.data_json or {}
        return data.get("variants", [])
    
    def _build_result(
        self,
        asset: Asset,
        match_type: str,
        confidence: float,
        time_of_day: Optional[str] = None,
        weather: Optional[str] = None,
    ) -> SceneMatchResult:
        """构建匹配结果，包含变体处理"""
        
        # 获取基础视觉提示词
        visual_prompt = self._get_visual_prompt(asset)
        
        # 查找变体
        variant = None
        if time_of_day or weather:
            variant = self._find_variant(asset, time_of_day, weather)
            
            # 如果有变体，追加 prompt modifier
            if variant and visual_prompt:
                visual_prompt = f"{visual_prompt}, {variant.prompt_modifier}"
            elif variant:
                visual_prompt = variant.prompt_modifier
        
        return SceneMatchResult(
            scene_id=asset.id,
            scene_name=asset.name,
            match_type=match_type,
            confidence=confidence,
            variant=variant,
            visual_prompt=visual_prompt
        )
    
    def _find_variant(
        self,
        asset: Asset,
        time_of_day: Optional[str],
        weather: Optional[str],
    ) -> Optional[SceneVariant]:
        """查找场景变体"""
        variants = self._get_variants(asset)
        
        # 构建条件字符串
        conditions = []
        if time_of_day:
            conditions.append(time_of_day)
        if weather:
            conditions.append(weather)
        
        condition_str = "_".join(conditions) if conditions else None
        
        if not condition_str:
            return None
        
        # 查找完全匹配的变体
        for v in variants:
            if v.get("condition") == condition_str:
                return SceneVariant(
                    condition=condition_str,
                    prompt_modifier=v.get("prompt_modifier", ""),
                    reference_image=v.get("reference_image")
                )
        
        # 查找部分匹配（只匹配时间或天气）
        for v in variants:
            if time_of_day and v.get("condition") == time_of_day:
                return SceneVariant(
                    condition=time_of_day,
                    prompt_modifier=v.get("prompt_modifier", ""),
                    reference_image=v.get("reference_image")
                )
            if weather and v.get("condition") == weather:
                return SceneVariant(
                    condition=weather,
                    prompt_modifier=v.get("prompt_modifier", ""),
                    reference_image=v.get("reference_image")
                )
        
        # 没有预定义变体，动态生成 prompt modifier
        modifier = self._generate_variant_modifier(time_of_day, weather)
        if modifier:
            return SceneVariant(
                condition=condition_str,
                prompt_modifier=modifier
            )
        
        return None
    
    def _generate_variant_modifier(
        self,
        time_of_day: Optional[str],
        weather: Optional[str],
    ) -> str:
        """动态生成变体的 prompt modifier"""
        modifiers = []
        
        if time_of_day:
            time_modifiers = {
                "day": "daytime, bright natural lighting, sunny",
                "night": "night time, dark atmosphere, artificial lights, moon light",
                "dawn": "dawn, early morning light, soft golden hour",
                "dusk": "dusk, sunset, warm orange lighting, evening atmosphere",
            }
            modifiers.append(time_modifiers.get(time_of_day, time_of_day))
        
        if weather:
            weather_modifiers = {
                "clear": "clear sky",
                "rain": "rainy, wet ground, rain drops, cloudy",
                "snow": "snowy, snow covered, winter atmosphere",
                "cloudy": "overcast, cloudy sky, diffused lighting",
            }
            modifiers.append(weather_modifiers.get(weather, weather))
        
        return ", ".join(modifiers)
    
    async def _semantic_match(
        self,
        description: str,
        scene_assets: List[Asset],
    ) -> Optional[Tuple[Asset, float]]:
        """使用 LLM 进行语义匹配"""
        if not scene_assets:
            return None
        
        asset_info = [
            {"id": a.id, "name": a.name, "aliases": self._get_aliases(a)}
            for a in scene_assets
        ]
        
        prompt = f"""判断以下地点描述是否与资产库中的某个场景相同或非常相似。

地点描述："{description}"

资产库场景：
{json.dumps([{"name": a["name"], "aliases": a["aliases"]} for a in asset_info], ensure_ascii=False, indent=2)}

请返回 JSON：
{{
    "matched": true/false,
    "scene_name": "匹配的场景名称（如果matched=true）",
    "confidence": 0.0-1.0 的置信度,
    "reason": "匹配原因"
}}

判断规则：
1. 如果描述明显指向同一地点（如 "老杂货铺" 和 "杂货铺内部"），返回 matched=true
2. 如果只是相似但不确定是同一地点，返回 matched=true 但 confidence 较低（0.5-0.7）
3. 如果是不同地点，返回 matched=false

只返回 JSON，不要其他内容。"""

        try:
            result = await self.llm._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json"
            )
            data = json.loads(result.strip())
            
            if data.get("matched") and data.get("scene_name"):
                matched_name = data["scene_name"]
                confidence = min(data.get("confidence", 0.6), 0.85)  # 语义匹配最高 0.85
                
                for asset in scene_assets:
                    if asset.name == matched_name:
                        return (asset, confidence)
                
                # 名称不完全匹配，尝试模糊查找
                for asset in scene_assets:
                    if matched_name in asset.name or asset.name in matched_name:
                        return (asset, confidence * 0.9)
            
            return None
            
        except Exception as e:
            logger.warning(f"SceneMatcher: LLM semantic match failed: {e}")
            return None
    
    async def batch_match(
        self,
        panels: List[Dict[str, Any]],
        project_assets: List[Asset],
    ) -> Dict[str, SceneMatchResult]:
        """批量匹配分镜场景
        
        Args:
            panels: 分镜列表，每个包含 scene_name, time_of_day, weather
            project_assets: 项目资产
        
        Returns:
            {panel_id: SceneMatchResult}
        """
        results = {}
        
        for panel in panels:
            panel_id = panel.get("id", "")
            scene_name = panel.get("scene_name") or panel.get("location", "")
            time_of_day = panel.get("time_of_day")
            weather = panel.get("weather")
            
            result = await self.match(
                description=scene_name,
                project_assets=project_assets,
                time_of_day=time_of_day,
                weather=weather,
            )
            
            results[panel_id] = result
        
        return results
