"""
SchemaGuard - Schema校验+自修复模块
用于验证JSON数据结构并在校验失败时自动调用LLM修复
"""
import logging
import json
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)


class SchemaType(str, Enum):
    """支持的Schema类型"""
    STORYBOARD = "storyboard"
    PANEL = "panel"
    CHARACTER = "character"
    SCENE = "scene"
    PROP = "prop"
    RENDER_PLAN = "render_plan"


class ValidationResult(BaseModel):
    """校验结果"""
    is_valid: bool = Field(..., description="是否校验通过")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    repaired_data: Optional[Dict[str, Any]] = Field(None, description="修复后的数据")


# Schema定义
SCHEMAS: Dict[str, Dict[str, Any]] = {
    SchemaType.PANEL: {
        "required": ["panel_number", "description"],
        "optional": ["dialogue", "camera", "characters", "scene", "props", "mood", "action"],
        "types": {
            "panel_number": int,
            "description": str,
            "dialogue": list,
            "camera": dict,
            "characters": list,
            "scene": str,
            "props": list,
            "mood": str,
            "action": str,
        },
        "nested": {
            "dialogue": {
                "required": ["speaker", "text"],
                "optional": ["emotion", "bubble_type"],
            },
            "camera": {
                "required": [],
                "optional": ["angle", "shot_type", "movement"],
            },
        },
    },
    SchemaType.STORYBOARD: {
        "required": ["panels"],
        "optional": ["title", "style", "characters", "scenes", "total_panels"],
        "types": {
            "panels": list,
            "title": str,
            "style": str,
            "characters": list,
            "scenes": list,
            "total_panels": int,
        },
    },
    SchemaType.CHARACTER: {
        "required": ["name"],
        "optional": ["description", "appearance", "personality", "visual_prompt", "reference_image"],
        "types": {
            "name": str,
            "description": str,
            "appearance": str,
            "personality": str,
            "visual_prompt": str,
            "reference_image": str,
        },
    },
    SchemaType.SCENE: {
        "required": ["name"],
        "optional": ["description", "visual_prompt", "time_of_day", "weather", "reference_image"],
        "types": {
            "name": str,
            "description": str,
            "visual_prompt": str,
            "time_of_day": str,
            "weather": str,
            "reference_image": str,
        },
    },
    SchemaType.PROP: {
        "required": ["name"],
        "optional": ["description", "visual_prompt", "category"],
        "types": {
            "name": str,
            "description": str,
            "visual_prompt": str,
            "category": str,
        },
    },
    SchemaType.RENDER_PLAN: {
        "required": ["panel_id", "workflow"],
        "optional": ["parameters", "retry_strategy", "priority", "dependencies"],
        "types": {
            "panel_id": str,
            "workflow": str,
            "parameters": dict,
            "retry_strategy": dict,
            "priority": int,
            "dependencies": list,
        },
    },
}


# 自动修复的System Prompt
REPAIR_SYSTEM_PROMPT = """你是一个JSON数据修复专家。用户会给你一个有问题的JSON数据和错误信息。

你的任务是：
1. 分析错误原因
2. 修复JSON数据使其符合Schema要求
3. 只返回修复后的JSON，不要有任何其他文字

Schema要求：
{schema_description}

请直接返回修复后的JSON。"""


class SchemaGuard:
    """Schema校验+自修复"""

    def __init__(self, auto_repair: bool = True):
        """
        初始化SchemaGuard
        
        Args:
            auto_repair: 是否在校验失败时自动尝试修复
        """
        self.auto_repair = auto_repair
        self.llm = StandardLLMService()

    def validate(
        self,
        data: Dict[str, Any],
        schema_type: SchemaType,
        strict: bool = False,
    ) -> ValidationResult:
        """
        验证数据是否符合Schema
        
        Args:
            data: 要验证的数据
            schema_type: Schema类型
            strict: 是否严格模式（严格模式下警告也会导致校验失败）
            
        Returns:
            ValidationResult
        """
        errors: List[str] = []
        warnings: List[str] = []

        if schema_type not in SCHEMAS:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown schema type: {schema_type}"],
            )

        schema = SCHEMAS[schema_type]

        # 检查必需字段
        for field in schema.get("required", []):
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif data[field] is None:
                errors.append(f"Required field '{field}' is null")

        # 检查字段类型
        type_specs = schema.get("types", {})
        for field, value in data.items():
            if field in type_specs and value is not None:
                expected_type = type_specs[field]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Field '{field}' has wrong type: expected {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )

        # 检查未知字段
        all_fields = set(schema.get("required", [])) | set(schema.get("optional", []))
        for field in data.keys():
            if field not in all_fields:
                warnings.append(f"Unknown field: {field}")

        # 检查嵌套结构
        nested_specs = schema.get("nested", {})
        for field, nested_schema in nested_specs.items():
            if field in data and data[field] is not None:
                nested_errors = self._validate_nested(
                    data[field], field, nested_schema
                )
                errors.extend(nested_errors)

        is_valid = len(errors) == 0
        if strict and len(warnings) > 0:
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    def _validate_nested(
        self,
        data: Any,
        field_name: str,
        nested_schema: Dict[str, Any],
    ) -> List[str]:
        """验证嵌套数据结构"""
        errors = []

        if isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    for req_field in nested_schema.get("required", []):
                        if req_field not in item:
                            errors.append(
                                f"{field_name}[{i}] missing required field: {req_field}"
                            )
        elif isinstance(data, dict):
            for req_field in nested_schema.get("required", []):
                if req_field not in data:
                    errors.append(f"{field_name} missing required field: {req_field}")

        return errors

    async def validate_and_repair(
        self,
        data: Dict[str, Any],
        schema_type: SchemaType,
        max_attempts: int = 2,
    ) -> ValidationResult:
        """
        验证数据，如果失败则尝试自动修复
        
        Args:
            data: 要验证的数据
            schema_type: Schema类型
            max_attempts: 最大修复尝试次数
            
        Returns:
            ValidationResult (可能包含修复后的数据)
        """
        result = self.validate(data, schema_type)

        if result.is_valid:
            return result

        if not self.auto_repair:
            return result

        # 尝试自动修复
        logger.info(f"Attempting auto-repair for {schema_type}, errors: {result.errors}")

        repaired_data = data.copy()
        for attempt in range(max_attempts):
            try:
                repaired_data = await self._repair_with_llm(
                    repaired_data, schema_type, result.errors
                )
                
                # 重新验证
                new_result = self.validate(repaired_data, schema_type)
                if new_result.is_valid:
                    logger.info(f"Auto-repair successful on attempt {attempt + 1}")
                    return ValidationResult(
                        is_valid=True,
                        errors=[],
                        warnings=new_result.warnings + [f"Data was auto-repaired (attempt {attempt + 1})"],
                        repaired_data=repaired_data,
                    )
                
                result = new_result
                
            except Exception as e:
                logger.error(f"Auto-repair attempt {attempt + 1} failed: {e}")

        # 所有修复尝试都失败了
        return ValidationResult(
            is_valid=False,
            errors=result.errors + ["Auto-repair failed after max attempts"],
            warnings=result.warnings,
            repaired_data=repaired_data,
        )

    async def _repair_with_llm(
        self,
        data: Dict[str, Any],
        schema_type: SchemaType,
        errors: List[str],
    ) -> Dict[str, Any]:
        """使用LLM修复数据"""
        schema = SCHEMAS.get(schema_type, {})
        
        schema_description = f"""
类型: {schema_type}
必需字段: {schema.get('required', [])}
可选字段: {schema.get('optional', [])}
字段类型要求: {schema.get('types', {})}
"""

        system_prompt = REPAIR_SYSTEM_PROMPT.format(schema_description=schema_description)

        user_message = f"""请修复以下JSON数据:

原始数据:
{json.dumps(data, ensure_ascii=False, indent=2)}

校验错误:
{chr(10).join(f"- {e}" for e in errors)}

请直接返回修复后的JSON，不要包含任何其他文字或markdown标记。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.llm._chat_completion(messages, response_format="json")

        # 解析修复后的JSON
        try:
            repaired = json.loads(response)
            return repaired
        except json.JSONDecodeError:
            # 尝试从response中提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse LLM repair response: {response}")

    def get_schema(self, schema_type: SchemaType) -> Dict[str, Any]:
        """获取指定类型的Schema定义"""
        return SCHEMAS.get(schema_type, {})

    @staticmethod
    def add_defaults(
        data: Dict[str, Any],
        schema_type: SchemaType,
    ) -> Dict[str, Any]:
        """为数据添加默认值"""
        schema = SCHEMAS.get(schema_type, {})
        result = data.copy()

        # 根据类型添加默认值
        defaults = {
            SchemaType.PANEL: {
                "dialogue": [],
                "characters": [],
                "props": [],
                "camera": {"angle": "eye_level", "shot_type": "medium"},
            },
            SchemaType.STORYBOARD: {
                "panels": [],
                "characters": [],
                "scenes": [],
            },
            SchemaType.CHARACTER: {
                "description": "",
                "appearance": "",
            },
            SchemaType.SCENE: {
                "description": "",
                "time_of_day": "day",
            },
            SchemaType.PROP: {
                "description": "",
                "category": "general",
            },
            SchemaType.RENDER_PLAN: {
                "parameters": {},
                "priority": 5,
                "dependencies": [],
            },
        }

        type_defaults = defaults.get(schema_type, {})
        for field, default_value in type_defaults.items():
            if field not in result:
                result[field] = default_value

        return result
