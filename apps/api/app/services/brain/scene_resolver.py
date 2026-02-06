"""
Scene Resolver - 场景去重与变体管理服务

解决问题：
1. 同一地点的不同描述被创建为多个资产
2. 不同时间/天气的场景需要不同渲染变体
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)


# 常见地点词缀（用于提取基础地点）
LOCATION_SUFFIXES = ["门口", "内部", "里面", "外面", "门前", "柜台前", "柜台", "角落", "中央", "入口", "出口"]
TIME_KEYWORDS = {
    "傍晚": "dusk", "夜晚": "night", "早晨": "morning", "上午": "morning",
    "中午": "noon", "下午": "afternoon", "黄昏": "dusk", "深夜": "late_night",
    "白天": "day", "清晨": "dawn", "黎明": "dawn"
}
LIGHTING_KEYWORDS = {
    "昏暗": "dim", "明亮": "bright", "阴暗": "dark", "温馨": "warm",
    "夕阳": "sunset", "灯笼光": "lantern", "月光": "moonlight",
    "阳光": "sunlight", "暮色": "twilight", "余晖": "afterglow"
}


class SceneResolver:
    """场景去重与变体管理"""
    
    def __init__(self, llm_service: Optional[StandardLLMService] = None):
        self.llm = llm_service or StandardLLMService()
    
    def parse_scene_description(self, description: str) -> Dict[str, Any]:
        """解析场景描述，提取结构化信息
        
        Args:
            description: 原始场景描述，如 "傍晚时分，杂货铺柜台前，光线昏暗..."
        
        Returns:
            {
                "base_location": "杂货铺",
                "sub_location": "柜台前",
                "time_of_day": "dusk",
                "lighting": "dim",
                "full_description": "原始描述",
                "variant_key": "dusk_dim"
            }
        """
        result = {
            "base_location": "",
            "sub_location": "",
            "time_of_day": "day",
            "lighting": "neutral",
            "full_description": description,
            "variant_key": ""
        }
        
        # 1. 提取时间
        for cn, en in TIME_KEYWORDS.items():
            if cn in description:
                result["time_of_day"] = en
                break
        
        # 2. 提取光照
        for cn, en in LIGHTING_KEYWORDS.items():
            if cn in description:
                result["lighting"] = en
                break
        
        # 3. 提取基础地点和子位置
        base_loc, sub_loc = self._extract_location(description)
        result["base_location"] = base_loc
        result["sub_location"] = sub_loc
        
        # 4. 生成变体键
        result["variant_key"] = f"{result['time_of_day']}_{result['lighting']}"
        
        return result
    
    def _extract_location(self, description: str) -> Tuple[str, str]:
        """从描述中提取基础地点和子位置
        
        Examples:
            "杂货铺柜台前" → ("杂货铺", "柜台前")
            "杂货铺门口" → ("杂货铺", "门口")
            "青石板巷" → ("青石板巷", "")
        """
        # 移除时间描述部分
        cleaned = description
        for time_word in TIME_KEYWORDS.keys():
            cleaned = cleaned.replace(time_word, "")
        cleaned = re.sub(r"时分[，,]?", "", cleaned)
        
        # 提取第一个逗号前的内容（通常是地点）
        parts = re.split(r"[，,。]", cleaned)
        location_part = parts[0].strip() if parts else cleaned
        
        # 检查是否包含子位置
        base_location = location_part
        sub_location = ""
        
        for suffix in LOCATION_SUFFIXES:
            if location_part.endswith(suffix):
                base_location = location_part[:-len(suffix)]
                sub_location = suffix
                break
        
        return base_location, sub_location
    
    def normalize_locations(self, locations: List[Dict]) -> List[Dict]:
        """规范化场景列表，去重并创建变体
        
        Args:
            locations: ScriptAnalysis 提取的原始 locations 列表
        
        Returns:
            规范化后的场景列表，包含 base_location 和 variants
        """
        # 按基础地点分组
        location_groups: Dict[str, List[Dict]] = {}
        
        for loc in locations:
            desc = loc.get("canonical_location", "") or loc.get("anchor_hint", "")
            parsed = self.parse_scene_description(desc)
            
            base = parsed["base_location"]
            if not base:
                base = desc[:10]  # 兜底：用前10个字作为基础地点
            
            if base not in location_groups:
                location_groups[base] = []
            
            location_groups[base].append({
                "original": loc,
                "parsed": parsed
            })
        
        # 构建规范化结果
        normalized = []
        for base_location, variants in location_groups.items():
            # 找到最详细的描述作为主描述
            primary = max(variants, key=lambda v: len(v["original"].get("anchor_hint", "")))
            
            # 收集所有变体
            variant_keys = set()
            sub_locations = set()
            for v in variants:
                variant_keys.add(v["parsed"]["variant_key"])
                if v["parsed"]["sub_location"]:
                    sub_locations.add(v["parsed"]["sub_location"])
            
            normalized.append({
                "canonical_location": base_location,
                "anchor_hint": primary["original"].get("anchor_hint", ""),
                "is_primary": primary["original"].get("is_primary", False),
                "first_appearance_span": primary["original"].get("first_appearance_span"),
                # 新增字段
                "sub_locations": list(sub_locations),
                "variants": list(variant_keys),
                "variant_count": len(variant_keys),
                "merged_from_count": len(variants)
            })
        
        logger.info(f"场景去重: {len(locations)} → {len(normalized)} (合并了 {len(locations) - len(normalized)} 个重复)")
        return normalized
    
    async def resolve_with_llm(self, locations: List[Dict]) -> List[Dict]:
        """使用 LLM 进行更智能的场景归一化
        
        用于场景名称差异较大但可能指同一地点的情况
        如: "老旧的杂货店" vs "杂货铺"
        """
        if len(locations) <= 1:
            return locations
        
        location_names = [loc.get("canonical_location", "") for loc in locations]
        
        prompt = f"""请判断以下场景名称是否指向同一个地点，并进行归一化。

场景列表：
{location_names}

请返回 JSON：
{{
    "groups": [
        {{
            "canonical_name": "规范化的地点名",
            "members": ["原始名1", "原始名2"]
        }}
    ]
}}

规则：
1. 同一地点的不同表述应合并 (如"杂货店"和"杂货铺")
2. 物理上不同的地点不要合并 (如"卧室"和"客厅")
3. 只返回 JSON"""

        try:
            result = await self.llm._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json"
            )
            import json
            data = json.loads(result.strip())
            
            # 应用 LLM 归一化结果
            name_mapping = {}
            for group in data.get("groups", []):
                canonical = group.get("canonical_name", "")
                for member in group.get("members", []):
                    name_mapping[member] = canonical
            
            # 更新 locations
            for loc in locations:
                original_name = loc.get("canonical_location", "")
                if original_name in name_mapping:
                    loc["original_name"] = original_name
                    loc["canonical_location"] = name_mapping[original_name]
            
            return locations
            
        except Exception as e:
            logger.warning(f"LLM 场景归一化失败: {e}")
            return locations
    
    def get_scene_asset_key(self, base_location: str, time_of_day: str = None, lighting: str = None) -> str:
        """生成场景资产的唯一键
        
        Args:
            base_location: 基础地点名
            time_of_day: 时间 (可选，用于变体)
            lighting: 光照 (可选，用于变体)
        
        Returns:
            资产唯一键，如 "杂货铺" 或 "杂货铺_dusk_dim"
        """
        key = base_location
        if time_of_day and time_of_day != "day":
            key += f"_{time_of_day}"
        if lighting and lighting != "neutral":
            key += f"_{lighting}"
        return key


def get_scene_resolver() -> SceneResolver:
    """获取场景解析器实例"""
    return SceneResolver()
