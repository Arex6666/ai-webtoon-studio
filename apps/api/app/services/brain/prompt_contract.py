"""
Prompt Contract - 统一的提示词合约数据结构

用于所有 LLM provider（OpenAI/通义/豆包/DeepSeek）。
支持 JSON 序列化、可回放、可追溯。
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal, Any, List
from datetime import datetime
import json


class PromptConstraints(BaseModel):
    """提示词约束配置"""
    target_panels_min: int = Field(default=4, ge=1, le=50)
    target_panels_max: int = Field(default=20, ge=1, le=100)
    target_total_duration_s_min: float = Field(default=30.0, ge=10.0)
    target_total_duration_s_max: float = Field(default=120.0, le=600.0)
    per_panel_duration_s_min: float = Field(default=1.5, ge=0.5)
    per_panel_duration_s_max: float = Field(default=8.0, le=15.0)


class StyleProfile(BaseModel):
    """风格配置"""
    name: str = "default"
    style_tags: List[str] = Field(default_factory=lambda: ["korean_webtoon"])
    palette: str = "warm"  # warm/cool/muted/vibrant
    line_weight: str = "medium"  # thin/medium/thick
    render_preset: str = "webtoon"  # webtoon/manga/realistic
    lighting_mood: str = "soft"  # soft/dramatic/natural
    
    def to_prompt_text(self) -> str:
        """转换为提示词文本"""
        return f"风格：{self.name}，标签：{', '.join(self.style_tags)}，色调：{self.palette}，线条：{self.line_weight}，渲染：{self.render_preset}，光线：{self.lighting_mood}"


class PromptMeta(BaseModel):
    """
    提示词元数据 - 用于回放和 A/B 测试
    
    保证：同输入同 digest
    """
    script_digest: str = Field(..., description="剧本文本的 SHA256 摘要")
    style_profile: Optional[StyleProfile] = Field(default=None)
    assets_digest: Optional[str] = Field(default=None, description="资产上下文的摘要")
    enum_digest: str = Field(..., description="枚举定义的摘要")
    constraints: PromptConstraints = Field(default_factory=PromptConstraints)
    
    # 可选追踪
    chapter_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PromptContract(BaseModel):
    """
    提示词合约 - 统一的提示词数据结构
    
    用于所有 LLM provider，保证可序列化、可回放、可追溯。
    """
    # 版本标识
    prompt_version: str = Field(
        default="pc_v1",
        description="提示词合约版本，如 'pc_v1'"
    )
    
    # 目标 Schema
    schema_target: Literal["script_analysis_v1", "storyboard_draft_v2"] = Field(
        ...,
        description="目标输出 Schema"
    )
    
    # 三段式提示词
    system: str = Field(
        ...,
        description="System prompt - 模型角色定义"
    )
    developer: str = Field(
        ...,
        description="Developer prompt - 规则和约束（含枚举列表、硬规则）"
    )
    user: str = Field(
        ...,
        description="User prompt - 具体输入（剧本、资产、约束）"
    )
    
    # 元数据
    meta: PromptMeta = Field(
        ...,
        description="元数据 - 用于回放和 A/B 测试"
    )
    
    def to_messages(self) -> List[Dict[str, str]]:
        """
        转换为 LLM API 兼容的消息格式
        
        OpenAI/DeepSeek 兼容格式
        """
        messages = [
            {"role": "system", "content": self.system}
        ]
        
        # Developer prompt 作为 system 的补充或用户消息的前置
        # 不同 provider 处理方式不同，这里合并到 system
        combined_system = f"{self.system}\n\n{self.developer}"
        messages[0]["content"] = combined_system
        
        messages.append({"role": "user", "content": self.user})
        
        return messages
    
    def to_messages_with_developer(self) -> List[Dict[str, str]]:
        """
        转换为三段式消息格式（支持 developer role 的 provider）
        """
        return [
            {"role": "system", "content": self.system},
            {"role": "developer", "content": self.developer},
            {"role": "user", "content": self.user}
        ]
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "PromptContract":
        """从 JSON 字符串反序列化"""
        return cls.model_validate_json(json_str)
    
    def get_digest(self) -> str:
        """获取整个 Contract 的摘要（用于版本比对）"""
        import hashlib
        content = f"{self.prompt_version}|{self.schema_target}|{self.meta.script_digest}|{self.meta.enum_digest}"
        if self.meta.assets_digest:
            content += f"|{self.meta.assets_digest}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# ============ 预设风格 ============

def get_default_style() -> StyleProfile:
    """默认风格：韩式条漫"""
    return StyleProfile(
        name="default",
        style_tags=["korean_webtoon", "soft_lighting", "emotional"],
        palette="warm",
        line_weight="medium",
        render_preset="webtoon",
        lighting_mood="soft"
    )


def get_rainy_soft_style() -> StyleProfile:
    """雨天柔和风格"""
    return StyleProfile(
        name="rainy_soft",
        style_tags=["rainy", "melancholic", "soft_focus", "blue_tones"],
        palette="cool",
        line_weight="thin",
        render_preset="webtoon",
        lighting_mood="soft"
    )


def get_cinematic_style() -> StyleProfile:
    """电影风格"""
    return StyleProfile(
        name="cinematic",
        style_tags=["cinematic", "dramatic_lighting", "high_contrast"],
        palette="muted",
        line_weight="thick",
        render_preset="realistic",
        lighting_mood="dramatic"
    )


STYLE_PRESETS = {
    "default": get_default_style,
    "rainy_soft": get_rainy_soft_style,
    "cinematic": get_cinematic_style,
}


def get_style_by_name(name: str) -> StyleProfile:
    """根据名称获取风格预设"""
    factory = STYLE_PRESETS.get(name, get_default_style)
    return factory()
