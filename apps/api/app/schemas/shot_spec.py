"""
ShotSpec Schema - 镜头规格（对齐设计文档）
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# ============ 枚举定义 ============

class ShotScale(str, Enum):
    """景别"""
    EXTREME_WIDE = "extreme_wide"   # 大远景
    WIDE = "wide"                   # 远景
    FULL = "full"                   # 全景
    MEDIUM = "medium"               # 中景
    MEDIUM_CLOSE = "medium_close"   # 中近景
    CLOSE = "close"                 # 近景
    EXTREME_CLOSE = "extreme_close" # 特写
    OVER_SHOULDER = "over_shoulder" # 过肩


class CameraMovement(str, Enum):
    """镜头运动"""
    STATIC = "static"       # 静止
    PUSH = "push"           # 推
    PULL = "pull"           # 拉
    PAN = "pan"             # 摇
    TILT = "tilt"           # 移
    TRACK = "track"         # 跟拍
    HANDHELD = "handheld"   # 手持


class LensType(str, Enum):
    """焦段倾向"""
    WIDE_ANGLE = "wide_angle"     # 广角（压迫感）
    NORMAL = "normal"             # 标准
    TELEPHOTO = "telephoto"       # 长焦（温柔/压缩）


class WeatherType(str, Enum):
    """天气类型"""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN_LIGHT = "rain_light"
    RAIN_HEAVY = "rain_heavy"
    SNOW = "snow"
    FOG = "fog"
    WIND = "wind"


class TimeOfDay(str, Enum):
    """时间段"""
    DAWN = "dawn"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    EVENING = "evening"
    NIGHT = "night"
    LATE_NIGHT = "late_night"


class ConsistencyLevel(str, Enum):
    """一致性强度"""
    STRICT = "strict"       # 强锁脸
    NORMAL = "normal"       # 正常
    FLEXIBLE = "flexible"   # 可变化


class ControlStrength(str, Enum):
    """控制强度"""
    STRONG = "strong"   # 强控
    MEDIUM = "medium"   # 中等
    WEAK = "weak"       # 弱控


class SeedPolicy(str, Enum):
    """种子策略"""
    FIXED = "fixed"     # 锁定（可复现）
    AUTO = "auto"       # 自动（多样性）


# ============ 子规格类 ============

class NarrativeSpec(BaseModel):
    """叙事意图"""
    purpose: str = Field(default="", description="本镜头要表达什么")
    emotion: str = Field(default="", description="情绪基调")
    key_props: List[str] = Field(default_factory=list, description="关键道具")
    key_actions: List[str] = Field(default_factory=list, description="关键动作")
    metaphor: Optional[str] = Field(default=None, description="隐喻/象征")


class CameraSpec(BaseModel):
    """运镜与镜头语言"""
    scale: ShotScale = Field(default=ShotScale.MEDIUM, description="景别")
    movement: CameraMovement = Field(default=CameraMovement.STATIC, description="镜头运动")
    lens: LensType = Field(default=LensType.NORMAL, description="焦段倾向")
    depth_of_field: float = Field(default=0.5, ge=0, le=1, description="景深 0=全清晰 1=强虚化")
    subject_position: List[float] = Field(default=[0.5, 0.5], description="主体位置 [x, y] 0-1")
    look_direction: str = Field(default="center", description="视线方向")
    headroom: float = Field(default=0.1, description="头顶留白比例")


class TimingSpec(BaseModel):
    """时间规格"""
    duration_s: float = Field(default=3.0, description="目标时长(秒)")
    fps: int = Field(default=24, description="目标帧率")
    keyframe_count: int = Field(default=1, description="关键帧数量")
    keyframe_strategy: str = Field(default="single", description="关键帧策略: single/start_end/start_mid_end")


class StyleSpec(BaseModel):
    """画风规格"""
    style_profile_id: Optional[str] = Field(default=None, description="风格配置ID")
    line_style: str = Field(default="clean", description="线条风格")
    color_style: str = Field(default="vibrant", description="上色风格")
    grain: float = Field(default=0.0, ge=0, le=1, description="颗粒感")
    color_palette: List[str] = Field(default_factory=list, description="色板")


class EnvironmentSpec(BaseModel):
    """环境/天气/光照"""
    weather: WeatherType = Field(default=WeatherType.CLEAR, description="天气")
    time_of_day: TimeOfDay = Field(default=TimeOfDay.AFTERNOON, description="时间段")
    light_sources: List[str] = Field(default_factory=list, description="光源")
    ambient_color: str = Field(default="#FFFFFF", description="环境光颜色")


class CharacterPlacement(BaseModel):
    """角色放置"""
    character_id: str = Field(..., description="角色资产ID")
    position: List[float] = Field(default=[0.5, 0.5], description="位置 [x, y] 0-1")
    scale: float = Field(default=1.0, description="缩放")
    pose: str = Field(default="standing", description="姿态")
    expression: str = Field(default="neutral", description="表情")
    variant: Optional[str] = Field(default=None, description="服装/发型变体")
    consistency: ConsistencyLevel = Field(default=ConsistencyLevel.NORMAL)


class CastSpec(BaseModel):
    """角色与一致性"""
    characters: List[CharacterPlacement] = Field(default_factory=list)


class SceneSpec(BaseModel):
    """场景与空间"""
    scene_id: Optional[str] = Field(default=None, description="场景资产ID")
    anchor_id: Optional[str] = Field(default=None, description="场景锚点ID")
    variable_elements: Dict[str, Any] = Field(default_factory=dict, description="可变元素")


class DialogueItem(BaseModel):
    """对话条目"""
    speaker_id: Optional[str] = Field(default=None, description="说话人ID")
    text: str = Field(default="", description="台词文本")
    tone: str = Field(default="normal", description="语气")
    bubble_style: str = Field(default="speech", description="气泡样式")
    position_hint: Optional[List[float]] = Field(default=None, description="位置提示")


class DialogueSpec(BaseModel):
    """对白与气泡"""
    dialogues: List[DialogueItem] = Field(default_factory=list)
    narration: Optional[str] = Field(default=None, description="旁白")
    sfx: List[str] = Field(default_factory=list, description="拟声词")


class ControlSpec(BaseModel):
    """控制图/参考图策略"""
    reference_images: List[str] = Field(default_factory=list, description="参考图路径")
    control_maps: Dict[str, str] = Field(default_factory=dict, description="控制图: depth/lineart/pose/canny")
    strength: ControlStrength = Field(default=ControlStrength.MEDIUM)


class EnginePlan(BaseModel):
    """引擎计划"""
    engine: str = Field(default="comfyui", description="引擎: comfyui/kling/tongyi/doubao")
    tier: str = Field(default="normal", description="档位: fast/normal/hero")
    seed_policy: SeedPolicy = Field(default=SeedPolicy.AUTO)
    seed: Optional[int] = Field(default=None, description="固定种子值")


# ============ 主 ShotSpec 类 ============

class ShotSpec(BaseModel):
    """镜头规格 - 完整的镜头合同"""
    shot_id: str = Field(..., description="镜头ID")
    order: int = Field(default=0, description="顺序")

    # 子规格
    narrative: NarrativeSpec = Field(default_factory=NarrativeSpec)
    camera: CameraSpec = Field(default_factory=CameraSpec)
    timing: TimingSpec = Field(default_factory=TimingSpec)
    style: StyleSpec = Field(default_factory=StyleSpec)
    environment: EnvironmentSpec = Field(default_factory=EnvironmentSpec)
    cast: CastSpec = Field(default_factory=CastSpec)
    scene: SceneSpec = Field(default_factory=SceneSpec)
    dialogue: DialogueSpec = Field(default_factory=DialogueSpec)
    control: ControlSpec = Field(default_factory=ControlSpec)
    engine_plan: EnginePlan = Field(default_factory=EnginePlan)

    # 额外数据
    extra: Dict[str, Any] = Field(default_factory=dict)
