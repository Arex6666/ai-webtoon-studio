"""
S5-01 - CharacterPortraitSpec Generator

从角色描述生成结构化的肖像规格，用于生成证件照式参考图。
"""

import json
import logging
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class CharacterPortraitSpec(BaseModel):
    """角色肖像规格"""
    character_id: str
    name: str
    gender: Literal["female", "male", "unknown"] = "unknown"
    age_range: Literal["teen", "young_adult", "adult", "middle_aged", "elder"] = "adult"
    hair: str = Field(min_length=6, description="头发描述，至少 6 字符")
    outfit: str = Field(min_length=6, description="服装描述，至少 6 字符")
    accessory: str = "none"
    notes: str = "no occlusion, no sunglasses/mask"
    style_profile: str = "A"
    
    @field_validator("hair", "outfit")
    @classmethod
    def validate_min_length(cls, v: str) -> str:
        if len(v.strip()) < 6:
            raise ValueError("描述太短，至少 6 字符")
        return v.strip()


# LLM Prompt
SPEC_GENERATION_PROMPT = '''你是一个专业的角色设定分析师。根据角色信息，生成用于绘制证件照/肖像画的结构化描述。

角色信息：
- 名称：{name}
- 描述：{description}
- 外貌特征：{traits}

请输出以下 JSON 格式：
{{
  "gender": "female" | "male" | "unknown",
  "age_range": "teen" | "young_adult" | "adult" | "middle_aged" | "elder",
  "hair": "详细的头发描述，例如：long black hair, low ponytail",
  "outfit": "上身服装描述，例如：light blue dress, beige knitted coat",
  "accessory": "配饰，如 earrings, glasses，没有则填 none",
  "notes": "绘制注意事项，例如：no occlusion, avoid covering eyes"
}}

要求：
1. hair 和 outfit 必须具体详细，至少 6 个英文单词
2. 所有描述用英文
3. 避免模糊词汇如 "normal", "standard"
4. 如果信息不足，合理推断但保守

只输出 JSON，不要其他内容。'''


async def generate_portrait_spec(
    character_id: str,
    character_name: str,
    character_description: Optional[str] = None,
    appearance_traits: Optional[List[str]] = None,
    style_profile: str = "A"
) -> CharacterPortraitSpec:
    """
    调用 LLM 生成角色肖像规格
    
    Args:
        character_id: 角色 ID
        character_name: 角色名称
        character_description: 角色描述（可选）
        appearance_traits: 外貌特征列表（可选）
        style_profile: 风格配置 ID
        
    Returns:
        CharacterPortraitSpec
    """
    from app.services.brain.base import get_brain_service
    
    # 准备 prompt
    description = character_description or "无详细描述"
    traits = ", ".join(appearance_traits) if appearance_traits else "无具体特征"
    
    prompt = SPEC_GENERATION_PROMPT.format(
        name=character_name,
        description=description,
        traits=traits
    )
    
    try:
        brain = get_brain_service()
        response = await brain._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format="json"
        )
        
        # 解析 JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            data = json.loads(response.strip())
        
        # 构建 Spec
        return CharacterPortraitSpec(
            character_id=character_id,
            name=character_name,
            gender=data.get("gender", "unknown"),
            age_range=data.get("age_range", "adult"),
            hair=data.get("hair", "dark hair, natural style"),
            outfit=data.get("outfit", "casual wear, simple shirt"),
            accessory=data.get("accessory", "none"),
            notes=data.get("notes", "no occlusion, no sunglasses/mask"),
            style_profile=style_profile
        )
        
    except Exception as e:
        logger.warning(f"[PortraitSpec] LLM 生成失败，使用默认值: {e}")
        # 返回基于名字的默认值
        return CharacterPortraitSpec(
            character_id=character_id,
            name=character_name,
            gender="unknown",
            age_range="adult",
            hair="dark hair, natural medium length",
            outfit="casual clothing, simple shirt",
            accessory="none",
            notes="no occlusion, frontal view",
            style_profile=style_profile
        )
