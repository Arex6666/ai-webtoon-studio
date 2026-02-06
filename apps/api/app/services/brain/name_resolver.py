"""
Name Resolver - 角色名称解析与合并服务

将同一角色的不同称呼（昵称、简称、别名）统一到正式名称。
"""
import logging
from typing import Dict, List, Optional, Set
from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)


class NameResolver:
    """角色名称解析与合并"""
    
    def __init__(self, llm_service: Optional[StandardLLMService] = None):
        self.llm = llm_service or StandardLLMService()
        
        # 常见中文昵称后缀
        self.nickname_suffixes = {"小", "阿", "老", "大"}
        # 常见昵称前缀
        self.nickname_prefixes = {"子", "儿", "哥", "姐", "弟", "妹"}
    
    async def resolve_aliases(
        self, 
        names: List[str],
        context: str = ""
    ) -> Dict[str, str]:
        """将昵称/简称映射到正式名称
        
        Args:
            names: 提取到的所有名称列表
            context: 剧本上下文（可选，用于 LLM 推断）
        
        Returns:
            映射字典 {昵称: 正式名称}
            例如: {"晓晓": "林晓", "小夏": "林知夏", "周屿": "周屿"}
        """
        if len(names) <= 1:
            return {name: name for name in names}
        
        # 第一步：规则匹配
        alias_map = {}
        full_names = set()
        potential_nicknames = []
        
        for name in names:
            # 假设 3 字以上为正式全名
            if len(name) >= 3:
                full_names.add(name)
            else:
                potential_nicknames.append(name)
        
        # 尝试规则匹配昵称到全名
        for nickname in potential_nicknames:
            matched = False
            for full_name in full_names:
                if self._is_nickname_of(nickname, full_name):
                    alias_map[nickname] = full_name
                    matched = True
                    break
            if not matched:
                # 无法匹配，保留原名
                alias_map[nickname] = nickname
        
        # 全名保持原样
        for full_name in full_names:
            alias_map[full_name] = full_name
        
        # 第二步：如果有上下文且规则无法解析，尝试 LLM
        unresolved = [n for n in potential_nicknames if alias_map.get(n) == n]
        if unresolved and context:
            try:
                llm_result = await self._llm_resolve(unresolved, list(full_names), context)
                alias_map.update(llm_result)
            except Exception as e:
                logger.warning(f"LLM 名称解析失败: {e}")
        
        return alias_map
    
    def _is_nickname_of(self, nickname: str, full_name: str) -> bool:
        """判断 nickname 是否为 full_name 的昵称"""
        # 例如: "晓晓" -> "林晓" (名字重叠)
        # 例如: "小夏" -> "林知夏" (最后一个字匹配)
        # 例如: "阿屿" -> "周屿" (去掉前缀后匹配)
        
        if len(nickname) < 1 or len(full_name) < 2:
            return False
        
        # 去掉昵称前缀后匹配
        if nickname[0] in self.nickname_suffixes and len(nickname) >= 2:
            core = nickname[1:]
            if core in full_name:
                return True
        
        # 叠字昵称匹配 (晓晓 -> 林晓)
        if len(nickname) == 2 and nickname[0] == nickname[1]:
            if nickname[0] in full_name:
                return True
        
        # 最后一个字匹配
        if nickname[-1] == full_name[-1] and len(nickname) <= 2:
            return True
        
        # 直接包含
        if nickname in full_name:
            return True
        
        return False
    
    async def _llm_resolve(
        self,
        nicknames: List[str],
        full_names: List[str],
        context: str
    ) -> Dict[str, str]:
        """使用 LLM 解析昵称"""
        prompt = f"""根据以下剧本内容，判断昵称列表中的每个昵称对应哪个正式名称。

剧本片段：
{context[:1000]}

正式名称列表：{full_names}
待解析昵称：{nicknames}

请返回 JSON 格式：{{"昵称1": "对应的正式名称", ...}}
如果无法确定，保持昵称原样。
只返回 JSON，不要解释。"""

        try:
            result = await self.llm._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json"
            )
            import json
            return json.loads(result.strip())
        except Exception as e:
            logger.error(f"LLM 名称解析异常: {e}")
            return {}
    
    async def merge_characters(
        self, 
        characters: List[dict]
    ) -> List[dict]:
        """合并指向同一人物的多个条目
        
        Args:
            characters: ScriptAnalysisV1 中的 characters 列表
        
        Returns:
            合并后的角色列表
        """
        if len(characters) <= 1:
            return characters
        
        # 提取所有名称
        names = [c.get("canonical_name", "") for c in characters]
        
        # 解析别名
        alias_map = await self.resolve_aliases(names)
        
        # 按正式名称分组
        grouped: Dict[str, List[dict]] = {}
        for char in characters:
            name = char.get("canonical_name", "")
            canonical = alias_map.get(name, name)
            if canonical not in grouped:
                grouped[canonical] = []
            grouped[canonical].append(char)
        
        # 合并每组
        merged = []
        for canonical, char_list in grouped.items():
            if len(char_list) == 1:
                merged.append(char_list[0])
            else:
                # 合并多个条目
                merged_char = self._merge_char_entries(canonical, char_list)
                merged.append(merged_char)
        
        return merged
    
    def _merge_char_entries(self, canonical_name: str, entries: List[dict]) -> dict:
        """合并多个角色条目为一个"""
        merged = {
            "canonical_name": canonical_name,
            "aliases": [],
            "appearance_traits": [],
            "personality_traits": [],
            "first_appearance_span": None,
        }
        
        seen_traits = set()
        
        for entry in entries:
            # 收集别名
            name = entry.get("canonical_name", "")
            if name != canonical_name and name not in merged["aliases"]:
                merged["aliases"].append(name)
            
            # 合并外观特征（去重）
            for trait in entry.get("appearance_traits", []):
                if trait not in seen_traits:
                    merged["appearance_traits"].append(trait)
                    seen_traits.add(trait)
            
            # 合并性格特征（去重）
            for trait in entry.get("personality_traits", []):
                if trait not in seen_traits:
                    merged["personality_traits"].append(trait)
                    seen_traits.add(trait)
            
            # 取第一个出现位置
            if not merged["first_appearance_span"]:
                merged["first_appearance_span"] = entry.get("first_appearance_span")
            
            # 复制其他字段
            for key in ["gender", "age_range", "role_type"]:
                if key not in merged or not merged.get(key):
                    merged[key] = entry.get(key)
        
        return merged
