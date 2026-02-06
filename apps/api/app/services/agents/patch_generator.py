"""
PatchGenerator - 补丁生成器模块
将用户自然语言指令转换为JSON Patch操作 (RFC 6902)
"""
import logging
import json
import re
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from enum import Enum

from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)


class PatchOperation(str, Enum):
    """JSON Patch操作类型 (RFC 6902)"""
    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"
    MOVE = "move"
    COPY = "copy"
    TEST = "test"


class PatchTarget(str, Enum):
    """Patch目标类型"""
    STORYBOARD = "storyboard"
    PANEL = "panel"
    SCRIPT = "script"
    CHARACTER = "character"
    SCENE = "scene"
    PROP = "prop"


class Patch(BaseModel):
    """单个Patch操作"""
    op: PatchOperation = Field(..., description="操作类型")
    path: str = Field(..., description="JSON Pointer路径")
    value: Optional[Any] = Field(None, description="新值 (add/replace需要)")
    from_path: Optional[str] = Field(None, description="源路径 (move/copy需要)")
    reason: str = Field("", description="修改原因说明")

    class Config:
        use_enum_values = True
        populate_by_name = True  # Allow both 'from_path' and 'from'


class PatchResult(BaseModel):
    """Patch生成结果"""
    success: bool = Field(..., description="是否成功生成")
    patches: List[Patch] = Field(default_factory=list, description="生成的Patch列表")
    target_type: PatchTarget = Field(..., description="Patch目标类型")
    summary: str = Field("", description="修改摘要")
    error: Optional[str] = Field(None, description="错误信息")


# Patch生成的System Prompt
PATCH_GENERATION_PROMPT = """你是一个专业的JSON Patch生成器。用户会给你当前数据状态和修改指令。

你的任务是生成符合RFC 6902规范的JSON Patch操作列表。

支持的操作:
- add: 添加新字段或数组元素
- remove: 删除字段或数组元素
- replace: 替换字段值
- move: 移动元素位置
- copy: 复制元素

路径格式 (JSON Pointer):
- 使用 / 分隔层级
- 数组索引用数字，如 /panels/0
- 使用 /- 表示数组末尾

返回格式 (JSON):
{
  "patches": [
    {
      "op": "replace",
      "path": "/panels/2/camera/angle",
      "value": "top_down",
      "reason": "用户要求改为俯视角"
    }
  ],
  "summary": "将第3格的镜头角度改为俯视"
}

注意:
1. path必须是有效的JSON Pointer
2. 数组索引从0开始
3. 每个patch都要有reason说明
4. 只返回JSON，不要有其他文字
"""


class PatchGenerator:
    """Patch生成器 - 将用户指令转换为JSON Patch"""

    def __init__(self):
        self.llm = StandardLLMService()

    async def generate_patch(
        self,
        user_instruction: str,
        current_state: Dict[str, Any],
        target_type: PatchTarget,
        context: Optional[Dict[str, Any]] = None,
    ) -> PatchResult:
        """
        根据用户指令生成JSON Patch
        
        Args:
            user_instruction: 用户的自然语言指令
            current_state: 当前数据状态
            target_type: 目标数据类型
            context: 额外上下文信息
            
        Returns:
            PatchResult
        """
        try:
            # 构建提示信息
            state_preview = self._get_state_preview(current_state, target_type)
            
            user_message = f"""当前数据类型: {target_type.value}

当前数据:
```json
{json.dumps(current_state, ensure_ascii=False, indent=2)}
```

{state_preview}

用户修改指令: {user_instruction}

请生成相应的JSON Patch操作。"""

            messages = [
                {"role": "system", "content": PATCH_GENERATION_PROMPT},
                {"role": "user", "content": user_message},
            ]

            response = await self.llm._chat_completion(messages, response_format="json")
            
            # 解析响应
            result_data = json.loads(response)
            
            patches = []
            for p in result_data.get("patches", []):
                patches.append(Patch(
                    op=PatchOperation(p["op"]),
                    path=p["path"],
                    value=p.get("value"),
                    from_path=p.get("from"),
                    reason=p.get("reason", ""),
                ))

            return PatchResult(
                success=True,
                patches=patches,
                target_type=target_type,
                summary=result_data.get("summary", ""),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse patch generation response: {e}")
            return PatchResult(
                success=False,
                patches=[],
                target_type=target_type,
                error=f"JSON解析失败: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Patch generation failed: {e}")
            return PatchResult(
                success=False,
                patches=[],
                target_type=target_type,
                error=str(e),
            )

    def _get_state_preview(
        self,
        state: Dict[str, Any],
        target_type: PatchTarget,
    ) -> str:
        """生成数据状态的友好预览"""
        preview_parts = []
        
        if target_type == PatchTarget.STORYBOARD:
            panels = state.get("panels", [])
            if panels:
                preview_parts.append(f"共有 {len(panels)} 格分镜:")
                for i, panel in enumerate(panels):
                    desc = panel.get("description", "无描述")[:50]
                    preview_parts.append(f"  第{i+1}格 (索引{i}): {desc}...")
                    
        elif target_type == PatchTarget.PANEL:
            panel_num = state.get("panel_number", "?")
            preview_parts.append(f"当前分镜: 第{panel_num}格")
            if "characters" in state:
                preview_parts.append(f"角色: {', '.join(state['characters'])}")
            if "scene" in state:
                preview_parts.append(f"场景: {state['scene']}")
                
        return "\n".join(preview_parts) if preview_parts else ""

    def apply_patches(
        self,
        target: Dict[str, Any],
        patches: List[Patch],
    ) -> Dict[str, Any]:
        """
        将Patch应用到目标数据
        
        Args:
            target: 目标数据
            patches: Patch列表
            
        Returns:
            修改后的数据
        """
        result = json.loads(json.dumps(target))  # 深拷贝
        
        for patch in patches:
            result = self._apply_single_patch(result, patch)
            
        return result

    def _apply_single_patch(
        self,
        target: Dict[str, Any],
        patch: Patch,
    ) -> Dict[str, Any]:
        """应用单个Patch"""
        path_parts = self._parse_json_pointer(patch.path)
        
        if patch.op == PatchOperation.ADD:
            return self._patch_add(target, path_parts, patch.value)
        elif patch.op == PatchOperation.REMOVE:
            return self._patch_remove(target, path_parts)
        elif patch.op == PatchOperation.REPLACE:
            return self._patch_replace(target, path_parts, patch.value)
        elif patch.op == PatchOperation.MOVE:
            from_parts = self._parse_json_pointer(patch.from_path or "")
            return self._patch_move(target, from_parts, path_parts)
        elif patch.op == PatchOperation.COPY:
            from_parts = self._parse_json_pointer(patch.from_path or "")
            return self._patch_copy(target, from_parts, path_parts)
        else:
            logger.warning(f"Unsupported patch operation: {patch.op}")
            return target

    def _parse_json_pointer(self, pointer: str) -> List[str]:
        """解析JSON Pointer为路径部分"""
        if not pointer or pointer == "/":
            return []
        
        # 移除开头的 /
        if pointer.startswith("/"):
            pointer = pointer[1:]
            
        # 处理转义字符
        parts = pointer.split("/")
        return [p.replace("~1", "/").replace("~0", "~") for p in parts]

    def _get_parent_and_key(
        self,
        target: Dict[str, Any],
        path_parts: List[str],
    ) -> tuple:
        """获取父对象和键名"""
        if not path_parts:
            return target, None
            
        current = target
        for part in path_parts[:-1]:
            if isinstance(current, list):
                current = current[int(part)]
            else:
                current = current[part]
        
        last_part = path_parts[-1]
        is_array_append = last_part == "-"
        
        if isinstance(current, list) and not is_array_append:
            return current, int(last_part)
        return current, last_part

    def _patch_add(
        self,
        target: Dict[str, Any],
        path_parts: List[str],
        value: Any,
    ) -> Dict[str, Any]:
        """ADD操作"""
        if not path_parts:
            return value
            
        parent, key = self._get_parent_and_key(target, path_parts)
        
        if isinstance(parent, list):
            if key == "-":
                parent.append(value)
            else:
                parent.insert(int(key), value)
        else:
            parent[key] = value
            
        return target

    def _patch_remove(
        self,
        target: Dict[str, Any],
        path_parts: List[str],
    ) -> Dict[str, Any]:
        """REMOVE操作"""
        if not path_parts:
            return {}
            
        parent, key = self._get_parent_and_key(target, path_parts)
        
        if isinstance(parent, list):
            del parent[int(key)]
        else:
            del parent[key]
            
        return target

    def _patch_replace(
        self,
        target: Dict[str, Any],
        path_parts: List[str],
        value: Any,
    ) -> Dict[str, Any]:
        """REPLACE操作"""
        if not path_parts:
            return value
            
        parent, key = self._get_parent_and_key(target, path_parts)
        parent[key] = value
        return target

    def _patch_move(
        self,
        target: Dict[str, Any],
        from_parts: List[str],
        to_parts: List[str],
    ) -> Dict[str, Any]:
        """MOVE操作"""
        if not from_parts:
            return target
            
        # 获取源值并删除
        from_parent, from_key = self._get_parent_and_key(target, from_parts)
        if isinstance(from_parent, list):
            idx = int(from_key) if not isinstance(from_key, int) else from_key
            value = from_parent[idx]
            del from_parent[idx]
        else:
            value = from_parent[from_key]
            del from_parent[from_key]
        
        # 添加到目标位置
        return self._patch_add(target, to_parts, value)

    def _patch_copy(
        self,
        target: Dict[str, Any],
        from_parts: List[str],
        to_parts: List[str],
    ) -> Dict[str, Any]:
        """COPY操作"""
        # 获取源值（深拷贝）
        from_parent, from_key = self._get_parent_and_key(target, from_parts)
        if isinstance(from_parent, list):
            value = json.loads(json.dumps(from_parent[int(from_key)]))
        else:
            value = json.loads(json.dumps(from_parent[from_key]))
        
        # 添加到目标位置
        return self._patch_add(target, to_parts, value)

    @staticmethod
    def create_simple_patch(
        op: PatchOperation,
        path: str,
        value: Any = None,
        reason: str = "",
    ) -> Patch:
        """便捷方法：创建简单Patch"""
        return Patch(
            op=op,
            path=path,
            value=value,
            reason=reason,
        )

    @staticmethod
    def patches_to_json(patches: List[Patch]) -> str:
        """将Patch列表转换为JSON字符串 (RFC 6902格式)"""
        result = []
        for p in patches:
            patch_dict = {"op": p.op, "path": p.path}
            if p.value is not None:
                patch_dict["value"] = p.value
            if p.from_path is not None:
                patch_dict["from"] = p.from_path  # RFC 6902 uses "from"
            if p.reason:
                patch_dict["reason"] = p.reason
            result.append(patch_dict)
        return json.dumps(result, ensure_ascii=False, indent=2)
