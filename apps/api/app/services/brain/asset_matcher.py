"""
Asset Matcher - 资产智能匹配服务

将分镜中的角色/场景名称智能匹配到项目资产库中的资产。
"""
import logging
from typing import Dict, Optional, List, Tuple
from app.services.brain.standard_llm import StandardLLMService
from app.services.brain.name_resolver import NameResolver
from app.models.asset import Asset

logger = logging.getLogger(__name__)


class AssetMatcher:
    """资产智能匹配器"""
    
    def __init__(
        self, 
        llm_service: Optional[StandardLLMService] = None,
        name_resolver: Optional[NameResolver] = None
    ):
        self.llm = llm_service or StandardLLMService()
        self.name_resolver = name_resolver or NameResolver()
    
    async def match_characters(
        self,
        panel_characters: List[str],
        project_assets: List[Asset]
    ) -> Dict[str, Optional[str]]:
        """匹配分镜角色 → 资产ID
        
        Args:
            panel_characters: 分镜中提到的角色名称列表
            project_assets: 项目中的所有资产
        
        Returns:
            匹配结果 {角色名: 资产ID 或 None}
        """
        # 筛选角色类型资产
        char_assets = [a for a in project_assets if a.asset_type == "character"]
        
        # 构建名称到资产的映射
        asset_name_map = {}
        for asset in char_assets:
            asset_name_map[asset.name] = asset.id
            # 也检查别名
            if asset.meta_json and "aliases" in asset.meta_json:
                for alias in asset.meta_json["aliases"]:
                    asset_name_map[alias] = asset.id
        
        matches = {}
        unmatched = []
        
        for char_name in panel_characters:
            # 1. 精确匹配
            if char_name in asset_name_map:
                matches[char_name] = asset_name_map[char_name]
                continue
            
            # 2. 别名匹配
            matched = False
            for asset_name, asset_id in asset_name_map.items():
                if self._is_alias_match(char_name, asset_name):
                    matches[char_name] = asset_id
                    matched = True
                    break
            
            if not matched:
                unmatched.append(char_name)
        
        # 3. 对于未匹配的，尝试 LLM 模糊匹配
        if unmatched and char_assets:
            llm_matches = await self._llm_match_characters(
                unmatched, 
                [a.name for a in char_assets]
            )
            for char_name, matched_name in llm_matches.items():
                if matched_name in asset_name_map:
                    matches[char_name] = asset_name_map[matched_name]
                else:
                    matches[char_name] = None  # 需要创建新资产
        else:
            for char_name in unmatched:
                matches[char_name] = None
        
        return matches
    
    async def match_scenes(
        self,
        panel_location: str,
        project_assets: List[Asset]
    ) -> Optional[str]:
        """匹配分镜场景 → 资产ID
        
        Args:
            panel_location: 分镜中的地点描述
            project_assets: 项目中的所有资产
        
        Returns:
            匹配的资产ID，或 None（需要创建新资产）
        """
        if not panel_location:
            return None
        
        # 筛选场景类型资产
        scene_assets = [a for a in project_assets if a.asset_type == "scene"]
        
        if not scene_assets:
            return None
        
        # 1. 精确匹配
        for asset in scene_assets:
            if asset.name == panel_location:
                return asset.id
        
        # 2. 包含匹配
        for asset in scene_assets:
            if asset.name in panel_location or panel_location in asset.name:
                return asset.id
        
        # 3. LLM 语义匹配
        return await self._llm_match_scene(
            panel_location,
            scene_assets
        )
    
    def _is_alias_match(self, name1: str, name2: str) -> bool:
        """判断两个名称是否为同一人物的别名"""
        # 叠字匹配: "晓晓" vs "林晓"
        if len(name1) == 2 and name1[0] == name1[1]:
            if name1[0] in name2:
                return True
        if len(name2) == 2 and name2[0] == name2[1]:
            if name2[0] in name1:
                return True
        
        # 包含匹配
        if len(name1) >= 2 and len(name2) >= 2:
            if name1 in name2 or name2 in name1:
                return True
        
        # 最后一个字匹配 (适合中文名)
        if name1[-1] == name2[-1] and len(name1) <= 2 and len(name2) >= 2:
            return True
        if name2[-1] == name1[-1] and len(name2) <= 2 and len(name1) >= 2:
            return True
        
        return False
    
    async def _llm_match_characters(
        self,
        unmatched_names: List[str],
        asset_names: List[str]
    ) -> Dict[str, Optional[str]]:
        """使用 LLM 进行模糊匹配"""
        if not unmatched_names or not asset_names:
            return {}
        
        prompt = f"""请判断以下分镜中的角色名是否与资产库中的某个角色是同一人物（可能是昵称、简称等）。

分镜中的角色名：{unmatched_names}
资产库中的角色：{asset_names}

请返回 JSON：
{{
    "分镜角色名1": "匹配的资产库角色名或null",
    "分镜角色名2": "匹配的资产库角色名或null"
}}

规则：
1. 如果是同一人物的不同称呼，返回对应的资产库角色名
2. 如果没有匹配，返回 null
3. 只返回 JSON"""

        try:
            result = await self.llm._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json"
            )
            import json
            return json.loads(result.strip())
        except Exception as e:
            logger.warning(f"LLM 角色匹配失败: {e}")
            return {}
    
    async def _llm_match_scene(
        self,
        location: str,
        scene_assets: List[Asset]
    ) -> Optional[str]:
        """使用 LLM 进行场景语义匹配"""
        if not scene_assets:
            return None
        
        asset_info = [{"id": a.id, "name": a.name} for a in scene_assets]
        
        prompt = f"""判断分镜中的地点描述是否与资产库中的某个场景匹配。

分镜地点：{location}
资产库场景：{[a["name"] for a in asset_info]}

请返回 JSON：
{{"matched_scene": "匹配的场景名或null"}}

只返回 JSON。"""

        try:
            result = await self.llm._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json"
            )
            import json
            data = json.loads(result.strip())
            matched_name = data.get("matched_scene")
            
            if matched_name:
                for asset in scene_assets:
                    if asset.name == matched_name:
                        return asset.id
            return None
        except Exception as e:
            logger.warning(f"LLM 场景匹配失败: {e}")
            return None
    
    async def auto_match_panel(
        self,
        panel: Dict,
        project_assets: List[Asset]
    ) -> Dict[str, any]:
        """自动匹配分镜中的所有资产引用
        
        Args:
            panel: 分镜数据，包含 characters, location 等
            project_assets: 项目资产列表
        
        Returns:
            匹配结果: {
                "characters": {角色名: 资产ID或None},
                "scene": 资产ID或None,
                "unmatched_characters": [未匹配的角色名],
                "unmatched_scene": bool
            }
        """
        result = {
            "characters": {},
            "scene": None,
            "unmatched_characters": [],
            "unmatched_scene": False
        }
        
        # 匹配角色
        panel_chars = panel.get("characters", [])
        if panel_chars:
            char_matches = await self.match_characters(panel_chars, project_assets)
            result["characters"] = char_matches
            result["unmatched_characters"] = [
                name for name, asset_id in char_matches.items() 
                if asset_id is None
            ]
        
        # 匹配场景
        location = panel.get("location", "")
        if location:
            scene_id = await self.match_scenes(location, project_assets)
            result["scene"] = scene_id
            result["unmatched_scene"] = scene_id is None
        
        return result
