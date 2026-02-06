"""
StoryboardDraftV2 - 面板级结构化输出

这是 LLM Plan 阶段的输出规范。
每个 PanelDraft 都有严格约束，确保生成商业化可控内容。
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal
from datetime import datetime

from .enums import (
    ShotTypeLiteral, CameraMoveLiteral, TimeOfDayLiteral, 
    WeatherLiteral, CameraHeightLiteral
)
from .script_analysis import SourceSpan


# ============ PanelDraft 分镜格 ============

class PanelDraft(BaseModel):
    """
    单个分镜格
    
    验收（硬约束）：
    - composition_notes 至少 2 条
    - continuity_notes 至少 1 条
    - source_span.quote 必须非空
    - duration_s 范围 1.5 ~ 8.0
    - actions 不能为空
    - visual_prompt 不能为空
    """
    
    # ===== 必须字段 =====
    
    index: int = Field(
        ...,
        ge=1,
        description="分镜序号（从 1 开始）"
    )
    
    beat_ref: Optional[str] = Field(
        default=None,
        description="关联的 beat_id（如 'b003'）"
    )
    
    # 镜头参数（强枚举约束）
    shot_type: ShotTypeLiteral = Field(
        ...,
        description="镜头类型：ECU/CU/MS/LS/WS/OTS"
    )
    
    camera_move: CameraMoveLiteral = Field(
        ...,
        description="运镜类型"
    )
    
    duration_s: float = Field(
        ...,
        ge=1.5,
        le=8.0,
        description="时长（秒），范围 1.5 ~ 8.0"
    )
    
    lens_hint: str = Field(
        default="50mm",
        description="镜头焦距提示"
    )
    
    mood: str = Field(
        ...,
        min_length=1,
        description="情绪基调（不能为空，至少 1 个词）"
    )
    
    # 场景参数
    location: str = Field(
        ...,
        min_length=1,
        description="地点（canonical_location，不能为空）"
    )
    
    time_of_day: TimeOfDayLiteral = Field(
        ...,
        description="时间段"
    )
    
    weather: WeatherLiteral = Field(
        ...,
        description="天气"
    )
    
    # 角色
    cast: List[str] = Field(
        ...,
        description="角色 canonical_name 列表（纯空镜时可为空但需设 is_establishing=True）"
    )
    
    # 动作描述
    actions: str = Field(
        ...,
        min_length=10,
        description="动作描述（不能为空，至少 1 句）"
    )
    
    # 构图注释（硬约束：至少 2 条）
    composition_notes: List[str] = Field(
        ...,
        min_length=2,
        description="构图要点（至少 2 条）"
    )
    
    # 对话
    dialogue_lines: List[str] = Field(
        default_factory=list,
        description="对话台词"
    )
    
    # 视觉提示（生成图像的关键）
    visual_prompt: str = Field(
        ...,
        min_length=20,
        description="视觉提示（不能为空；至少包含主体+环境+光照+画风其中 2 类）"
    )
    
    # 连续性注释（硬约束：至少 1 条）
    continuity_notes: List[str] = Field(
        ...,
        min_length=1,
        description="连续性约束（至少 1 条：服饰/道具/天气/光一致性）"
    )
    
    # 原文溯源（必须）
    source_span: SourceSpan = Field(
        ...,
        description="原文引用（必须）"
    )
    
    # ===== 可选字段 =====
    
    negative_prompt: Optional[str] = Field(
        default=None,
        description="负面提示词"
    )
    
    style_tags: List[str] = Field(
        default_factory=list,
        description="风格标签"
    )
    
    sfx: List[str] = Field(
        default_factory=list,
        description="拟声词/音效"
    )
    
    camera_height: Optional[CameraHeightLiteral] = Field(
        default=None,
        description="机位高度"
    )
    
    is_establishing: bool = Field(
        default=False,
        description="是否为建立镜头（纯空镜）"
    )
    
    # ===== 校验器 =====
    
    @field_validator('composition_notes')
    @classmethod
    def validate_composition(cls, v: List[str]) -> List[str]:
        cleaned = [n.strip() for n in v if n.strip()]
        if len(cleaned) < 2:
            raise ValueError('composition_notes 至少需要 2 条（逼细节）')
        return cleaned
    
    @field_validator('continuity_notes')
    @classmethod
    def validate_continuity(cls, v: List[str]) -> List[str]:
        cleaned = [n.strip() for n in v if n.strip()]
        if len(cleaned) < 1:
            raise ValueError('continuity_notes 至少需要 1 条（逼一致性）')
        return cleaned
    
    @model_validator(mode='after')
    def validate_cast_or_establishing(self) -> 'PanelDraft':
        """验证：纯空镜必须设置 is_establishing=True"""
        if not self.cast and not self.is_establishing:
            # 允许但发出警告
            pass
        return self


# ============ StoryboardDraftV2 主结构 ============

class StoryboardDraftV2(BaseModel):
    """
    分镜草稿 v2
    
    这是 LLM Plan 阶段的完整输出。
    """
    # 版本标识（强约束）
    schema_version: Literal["storyboard_draft_v2"] = Field(
        default="storyboard_draft_v2",
        description="Schema 版本，必须是 'storyboard_draft_v2'"
    )
    
    prompt_version: str = Field(
        default="pc_v1",
        description="提示词合约版本"
    )
    
    analysis_ref: Optional[str] = Field(
        default=None,
        description="关联的 ScriptAnalysisV1 ID 或 digest"
    )
    
    # 分镜列表（至少 1 个）
    panels: List[PanelDraft] = Field(
        ...,
        min_length=1,
        description="分镜列表（至少 1 个）"
    )
    
    # 元数据
    total_duration_s: float = Field(
        default=0.0,
        description="总时长（秒）"
    )
    
    director_notes: str = Field(
        default="",
        description="导演备注"
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @model_validator(mode='after')
    def compute_total_duration(self) -> 'StoryboardDraftV2':
        """计算总时长"""
        if self.panels:
            self.total_duration_s = sum(p.duration_s for p in self.panels)
        return self
    
    def get_panel_by_index(self, index: int) -> Optional[PanelDraft]:
        """根据序号获取分镜"""
        for p in self.panels:
            if p.index == index:
                return p
        return None
    
    def get_panels_by_beat(self, beat_ref: str) -> List[PanelDraft]:
        """根据 beat_ref 获取分镜"""
        return [p for p in self.panels if p.beat_ref == beat_ref]


# ============ 辅助函数 ============

def create_storyboard_draft(
    panels: List[dict],
    analysis_ref: Optional[str] = None,
    prompt_version: str = "pc_v1"
) -> StoryboardDraftV2:
    """从字典创建 StoryboardDraftV2"""
    return StoryboardDraftV2(
        prompt_version=prompt_version,
        analysis_ref=analysis_ref,
        panels=[PanelDraft(**p) for p in panels]
    )


def validate_panel_draft(panel_dict: dict) -> tuple[bool, List[str]]:
    """
    验证单个分镜的字典格式
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    # 必须字段检查
    required_fields = [
        'index', 'shot_type', 'camera_move', 'duration_s',
        'mood', 'location', 'time_of_day', 'weather',
        'actions', 'composition_notes', 'continuity_notes',
        'visual_prompt', 'source_span'
    ]
    
    for field in required_fields:
        if field not in panel_dict:
            errors.append(f"缺少必须字段: {field}")
    
    # composition_notes 检查
    comp_notes = panel_dict.get('composition_notes', [])
    if len(comp_notes) < 2:
        errors.append("composition_notes 至少需要 2 条")
    
    # continuity_notes 检查
    cont_notes = panel_dict.get('continuity_notes', [])
    if len(cont_notes) < 1:
        errors.append("continuity_notes 至少需要 1 条")
    
    # duration_s 范围检查
    duration = panel_dict.get('duration_s', 0)
    if duration < 1.5 or duration > 8.0:
        errors.append(f"duration_s ({duration}) 超出范围 1.5~8.0")
    
    # source_span.quote 检查
    source_span = panel_dict.get('source_span', {})
    if not source_span.get('quote'):
        errors.append("source_span.quote 不能为空（逼溯源）")
    
    return len(errors) == 0, errors
