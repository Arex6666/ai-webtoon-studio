"""
Portrait Service - S5-01 角色参考图自动生成

子模块：
- spec_generator: LLM → CharacterPortraitSpec
- prompt_composer: Spec → 图像生成 prompt
- portrait_generator: 图像生成
- portrait_qa: Face QA 验证
- retry_strategy: 失败重试
"""

from .spec_generator import CharacterPortraitSpec, generate_portrait_spec
from .portrait_qa import PortraitQAResult, validate_portrait
from .portrait_generator import generate_character_portrait, PortraitResult
from .retry_strategy import generate_with_retry

__all__ = [
    "CharacterPortraitSpec",
    "generate_portrait_spec",
    "PortraitQAResult",
    "validate_portrait",
    "generate_character_portrait",
    "PortraitResult",
    "generate_with_retry",
]
