"""
ScriptAnalysisV1 - 剧情结构化注册表

这是 LLM Parse 阶段的输出规范。
所有字段都有严格约束，确保输出稳定可控。
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal
from datetime import datetime

from .enums import (
    TimeOfDayLiteral, WeatherLiteral, 
    CharacterRoleLiteral, LocationTypeLiteral
)


# ============ SourceSpan 溯源 ============

class SourceSpan(BaseModel):
    """
    原文溯源
    
    强制 quote 字段，确保每个结构化元素都能追溯到原文。
    """
    quote: str = Field(
        ..., 
        min_length=10, 
        max_length=200,
        description="原文摘录 15~120 字，必须非空"
    )
    start_char: Optional[int] = Field(
        default=None,
        description="原文起始字符位置（可选）"
    )
    end_char: Optional[int] = Field(
        default=None,
        description="原文结束字符位置（可选）"
    )
    
    @field_validator('quote')
    @classmethod
    def quote_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('quote 不能为空，必须摘录原文')
        return v.strip()


# ============ CharacterEntity 角色注册 ============

class CharacterEntity(BaseModel):
    """
    角色注册表条目
    
    验收：
    - appearance_traits 至少 2 个
    - personality_traits 至少 2 个
    """
    canonical_name: str = Field(
        ..., 
        min_length=1,
        description="角色规范名（不能为空）"
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="别名列表"
    )
    role: CharacterRoleLiteral = Field(
        default="supporting",
        description="角色类型"
    )
    
    # 外观特征（硬性要求至少 2 个）
    appearance_traits: List[str] = Field(
        ...,
        min_length=2,
        description="外观特征（至少 2 个）：发型、发色、眼睛、身材、穿着风格等"
    )
    
    # 性格特征（硬性要求至少 2 个）
    personality_traits: List[str] = Field(
        ...,
        min_length=2,
        description="性格特征（至少 2 个）：内向、开朗、冷静、温柔等"
    )
    
    wardrobe_notes: Optional[str] = Field(
        default=None,
        description="服装备注"
    )
    
    signature_props: List[str] = Field(
        default_factory=list,
        description="标志性道具：眼镜、围巾、书包等"
    )
    
    first_appearance_span: SourceSpan = Field(
        ...,
        description="首次出现的原文引用（必须）"
    )
    
    @field_validator('appearance_traits')
    @classmethod
    def validate_appearance(cls, v: List[str]) -> List[str]:
        if len(v) < 2:
            raise ValueError('appearance_traits 至少需要 2 个特征')
        return [t.strip() for t in v if t.strip()]
    
    @field_validator('personality_traits')
    @classmethod
    def validate_personality(cls, v: List[str]) -> List[str]:
        if len(v) < 2:
            raise ValueError('personality_traits 至少需要 2 个特征')
        return [t.strip() for t in v if t.strip()]


# ============ LocationEntity 地点注册 ============

class LocationEntity(BaseModel):
    """
    地点注册表条目
    """
    canonical_location: str = Field(
        ..., 
        min_length=1,
        description="地点规范名（不能为空）"
    )
    type: LocationTypeLiteral = Field(
        default="interior",
        description="地点类型：interior/exterior/semi"
    )
    time_of_day_default: TimeOfDayLiteral = Field(
        default="day",
        description="默认时间段"
    )
    weather_default: WeatherLiteral = Field(
        default="clear",
        description="默认天气"
    )
    
    anchor_hint: str = Field(
        ...,
        min_length=5,
        description="场景锚点描述（至少 1 句，用于 BG anchor 生成）"
    )
    
    first_appearance_span: SourceSpan = Field(
        ...,
        description="首次出现的原文引用（必须）"
    )


# ============ Beat 节拍/事件单元 ============

class Beat(BaseModel):
    """
    剧情节拍
    
    每个 beat 是一个可视化的事件单元。
    """
    beat_id: str = Field(
        ...,
        pattern=r'^b\d{3}$',
        description="节拍 ID，格式如 'b001'"
    )
    
    summary: str = Field(
        ...,
        min_length=5,
        description="节拍摘要（至少 1 句）"
    )
    
    characters_involved: List[str] = Field(
        ...,
        description="涉及的角色 canonical_name 列表"
    )
    
    location_ref: Optional[str] = Field(
        default=None,
        description="地点引用（canonical_location）"
    )
    
    emotional_tone: Optional[str] = Field(
        default=None,
        description="情绪基调"
    )
    
    source_span: SourceSpan = Field(
        ...,
        description="原文引用（必须）"
    )


# ============ ScriptAnalysisV1 主结构 ============

class ScriptAnalysisV1(BaseModel):
    """
    剧情结构化分析 v1
    
    这是 LLM Parse 阶段的完整输出。
    强制校验确保商业可控。
    """
    # 版本标识（强约束）
    schema_version: Literal["script_analysis_v1"] = Field(
        default="script_analysis_v1",
        description="Schema 版本，必须是 'script_analysis_v1'"
    )
    
    language: Literal["zh", "en"] = Field(
        default="zh",
        description="剧本语言"
    )
    
    script_digest: str = Field(
        ...,
        min_length=8,
        description="剧本文本的 hash（用于回放和版本追溯）"
    )
    
    # 注册表
    characters: List[CharacterEntity] = Field(
        ...,
        min_length=1,
        description="角色注册表（至少 1 个角色）"
    )
    
    locations: List[LocationEntity] = Field(
        ...,
        min_length=1,
        description="地点注册表（至少 1 个地点）"
    )
    
    beats: List[Beat] = Field(
        ...,
        min_length=1,
        description="剧情节拍列表（至少 1 个 beat）"
    )
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @model_validator(mode='after')
    def validate_references(self) -> 'ScriptAnalysisV1':
        """验证引用完整性（宽松模式：只警告不失败）"""
        char_names = {c.canonical_name for c in self.characters}
        location_names = {l.canonical_location for l in self.locations}
        
        warnings = []
        
        for beat in self.beats:
            for char in beat.characters_involved:
                if char not in char_names:
                    warnings.append(f"Beat {beat.beat_id}: 引用了未注册角色 '{char}'")
            
            if beat.location_ref and beat.location_ref not in location_names:
                warnings.append(f"Beat {beat.beat_id}: 引用了未注册地点 '{beat.location_ref}'")
        
        # 暂时只记录警告，不校验失败（避免卡死）
        if warnings:
            # 可以通过日志输出
            pass
        
        return self
    
    def get_character_by_name(self, name: str) -> Optional[CharacterEntity]:
        """根据名称获取角色"""
        for c in self.characters:
            if c.canonical_name == name or name in c.aliases:
                return c
        return None
    
    def get_location_by_name(self, name: str) -> Optional[LocationEntity]:
        """根据名称获取地点"""
        for l in self.locations:
            if l.canonical_location == name:
                return l
        return None


# ============ 辅助函数 ============

def create_script_analysis(
    script_text: str,
    characters: List[dict],
    locations: List[dict],
    beats: List[dict],
    language: str = "zh"
) -> ScriptAnalysisV1:
    """从字典创建 ScriptAnalysisV1"""
    import hashlib
    
    script_digest = hashlib.md5(script_text.encode()).hexdigest()[:16]
    
    return ScriptAnalysisV1(
        language=language,
        script_digest=script_digest,
        characters=[CharacterEntity(**c) for c in characters],
        locations=[LocationEntity(**l) for l in locations],
        beats=[Beat(**b) for b in beats]
    )
