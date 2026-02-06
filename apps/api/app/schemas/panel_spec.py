"""
PanelSpec JSON Schema - 分镜规格定义
Single Source of Truth for panel content and generation parameters

遵循规范：每格必须包含最小字段集
- panel_id, order, title?, summary?
- characters: [{character_id, name, outfit_id?, expression_id?, pose_id?, importance?}]
- scene: {scene_id, name, time_of_day?, weather?, reuse_anchor?}
- composition: {shot_size, camera_angle, perspective_level, subject_position_9grid, leave_space_regions?}
- dialogue: [{type: narration|speech, speaker?, text, emotion_tag}]
- bubble_plan: draft + final
- prompt: {positive, negative, weights}
- render_tier: hero|normal|fast
- warnings: [{code, message, severity, target_ref}]
- render: {latest_layerpack_id?, qa_score?, status?}
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime


# ===== 枚举定义 =====

class ShotType(str, Enum):
    """景别类型"""
    EXTREME_CLOSE = "extreme_close"  # 特写
    CLOSE = "close"                   # 近景
    MEDIUM_CLOSE = "medium_close"     # 中近景
    MEDIUM = "medium"                 # 中景
    MEDIUM_FULL = "medium_full"       # 中全景
    FULL = "full"                     # 全身
    WIDE = "wide"                     # 远景
    EXTREME_WIDE = "extreme_wide"     # 大远景


class CameraAngle(str, Enum):
    """镜头角度"""
    EYE_LEVEL = "eye_level"      # 平视
    HIGH = "high"                 # 俯视
    LOW = "low"                   # 仰视
    BIRD = "bird"                 # 鸟瞰
    WORM = "worm"                 # 蚁视
    DUTCH = "dutch"               # 荷兰角（倾斜）


class DialogueType(str, Enum):
    """对话类型"""
    SPEECH = "speech"            # 普通对话
    NARRATION = "narration"      # 旁白
    THOUGHT = "thought"          # 内心独白
    PHONE = "phone"              # 电话
    SHOUT = "shout"              # 喊叫
    WHISPER = "whisper"          # 低语
    SFX = "sfx"                  # 音效


class BubbleStyle(str, Enum):
    """气泡样式"""
    NORMAL = "normal"            # 普通对话框
    SHOUT = "shout"              # 喊叫框（爆炸形）
    WHISPER = "whisper"          # 低语框（虚线）
    THOUGHT = "thought"          # 思考框（云朵）
    NARRATION = "narration"      # 旁白框（矩形）
    PHONE = "phone"              # 电话框
    ELECTRONIC = "electronic"    # 电子屏幕框
    FLASH = "flash"              # 闪回框
    TREMBLING = "trembling"      # 颤抖框
    HEART = "heart"              # 心形框


class NineGrid(str, Enum):
    """九宫格位置"""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_CENTER = "middle_center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class RenderTier(str, Enum):
    """渲染级别"""
    HERO = "hero"          # 重点分镜（高质量）
    NORMAL = "normal"      # 普通分镜
    FAST = "fast"          # 快速渲染（低质量）


class WarningSeverity(str, Enum):
    """警告级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PanelStatus(str, Enum):
    """分镜状态"""
    DRAFT = "draft"                # 草稿
    QUEUED = "queued"              # 排队中
    RENDERING = "rendering"        # 渲染中
    RENDERED = "rendered"          # 已渲染
    NEEDS_FIX = "needs_fix"        # 需要修复
    APPROVED = "approved"          # 已批准


# ===== 子模型定义 =====

class CharacterRef(BaseModel):
    """角色引用 - 分镜中的角色配置"""
    character_id: str = Field(..., description="角色资产 ID")
    name: str = Field(..., description="角色名称（用于显示）")
    outfit_id: Optional[str] = Field(default=None, description="服装预设 ID")
    expression_id: Optional[str] = Field(default=None, description="表情预设 ID")
    pose_id: Optional[str] = Field(default=None, description="姿势预设 ID")
    importance: Literal["primary", "secondary", "background"] = Field(
        default="primary", description="角色重要性"
    )
    position: Optional[NineGrid] = Field(default=None, description="九宫格位置")
    scale: float = Field(default=1.0, ge=0.1, le=3.0, description="缩放比例")
    flip_horizontal: bool = Field(default=False, description="水平翻转")
    layer_order: int = Field(default=0, description="图层顺序")
    
    class Config:
        use_enum_values = True


class SceneRef(BaseModel):
    """场景引用 - 分镜中的场景配置"""
    scene_id: Optional[str] = Field(default=None, description="场景资产 ID（可空表示新场景）")
    name: str = Field(default="", description="场景名称")
    time_of_day: Literal["day", "night", "dawn", "dusk", "noon", "midnight"] = Field(
        default="day", description="时间"
    )
    weather: Literal["clear", "cloudy", "rain", "snow", "fog", "storm"] = Field(
        default="clear", description="天气"
    )
    reuse_anchor: bool = Field(default=True, description="是否复用场景锚点（一致性）")
    location_description: str = Field(default="", description="场景描述文本")


class CompositionSettings(BaseModel):
    """构图设置"""
    shot_size: ShotType = Field(default=ShotType.MEDIUM, description="景别")
    camera_angle: CameraAngle = Field(default=CameraAngle.EYE_LEVEL, description="角度")
    perspective_level: float = Field(default=0.3, ge=0, le=1, description="透视强度")
    subject_position: NineGrid = Field(default=NineGrid.MIDDLE_CENTER, description="主体位置")
    leave_space_regions: List[str] = Field(
        default_factory=list, 
        description="留白区域（用于气泡）: ['top', 'bottom', 'left', 'right']"
    )
    depth_of_field: float = Field(default=0.5, ge=0, le=1, description="景深强度")
    
    class Config:
        use_enum_values = True


class DialogueLine(BaseModel):
    """对话条目"""
    id: str = Field(..., description="对话 ID")
    type: DialogueType = Field(default=DialogueType.SPEECH, description="对话类型")
    speaker_id: Optional[str] = Field(default=None, description="说话角色 ID")
    speaker_name: Optional[str] = Field(default=None, description="说话角色名（显示用）")
    text: str = Field(..., description="对话文本")
    emotion_tag: Optional[str] = Field(default=None, description="情绪标签")
    
    class Config:
        use_enum_values = True


class BubbleDraft(BaseModel):
    """气泡草稿 - AI 自动定位前"""
    dialogue_id: str = Field(..., description="关联的对话 ID")
    candidate_regions: List[str] = Field(
        default_factory=lambda: ["top", "auto"],
        description="候选区域"
    )
    style_hint: BubbleStyle = Field(default=BubbleStyle.NORMAL, description="样式提示")
    
    class Config:
        use_enum_values = True


class BubbleFinal(BaseModel):
    """气泡最终位置 - 用户确认后"""
    dialogue_id: str = Field(..., description="关联的对话 ID")
    x: float = Field(..., ge=0, le=1, description="X 坐标（百分比）")
    y: float = Field(..., ge=0, le=1, description="Y 坐标（百分比）")
    width: float = Field(default=0.3, ge=0.1, le=0.9, description="宽度（百分比）")
    height: Optional[float] = Field(default=None, description="高度（百分比，可自动）")
    bubble_style_id: str = Field(default="normal", description="气泡样式 ID")
    rotation: float = Field(default=0, ge=-45, le=45, description="旋转角度")
    z_index: int = Field(default=100, description="层级")
    font_size: int = Field(default=24, ge=12, le=72, description="字体大小")
    is_vertical: bool = Field(default=False, description="是否竖排")


class BubblePlan(BaseModel):
    """气泡计划"""
    draft: List[BubbleDraft] = Field(default_factory=list, description="草稿（AI 生成）")
    final: List[BubbleFinal] = Field(default_factory=list, description="最终（用户确认）")


class PromptSettings(BaseModel):
    """提示词设置"""
    positive: str = Field(default="", description="正向提示词")
    negative: str = Field(
        default="text, watermark, signature, blurry, low quality, bad anatomy, extra limbs",
        description="负向提示词"
    )
    style_strength: float = Field(default=0.8, ge=0, le=1.5, description="风格强度")
    lineart_strength: float = Field(default=0.7, ge=0, le=1.5, description="线稿强度")
    exaggeration: float = Field(default=0.3, ge=0, le=1, description="夸张程度")


class Warning(BaseModel):
    """警告信息"""
    code: str = Field(..., description="警告代码")
    message: str = Field(..., description="警告信息")
    severity: WarningSeverity = Field(default=WarningSeverity.WARNING, description="严重程度")
    target_ref: Optional[str] = Field(default=None, description="目标引用 (character_id/dialogue_id)")
    auto_fixable: bool = Field(default=False, description="是否可自动修复")
    suggested_fix: Optional[str] = Field(default=None, description="建议修复方案")
    
    class Config:
        use_enum_values = True


class RenderInfo(BaseModel):
    """渲染信息"""
    latest_layerpack_id: Optional[str] = Field(default=None, description="最新图层包 ID")
    qa_score: float = Field(default=0.0, ge=0, le=1, description="QA 评分")
    status: PanelStatus = Field(default=PanelStatus.DRAFT, description="渲染状态")
    preview_url: Optional[str] = Field(default=None, description="预览图 URL")
    rendered_at: Optional[datetime] = Field(default=None, description="渲染时间")
    retry_count: int = Field(default=0, description="重试次数")
    
    class Config:
        use_enum_values = True


class LookSettings(BaseModel):
    """画风设置 - 导演语言"""
    style_profile_id: Optional[str] = Field(default=None, description="风格预设资产 ID")
    style_preset: str = Field(default="korean_webtoon", description="风格预设名称")
    line_hardness: float = Field(default=0.5, ge=0, le=1, description="线条硬朗度")
    coloring_density: float = Field(default=0.5, ge=0, le=1, description="上色密度")
    screentone_intensity: float = Field(default=0.0, ge=0, le=1, description="网点强度")
    texture: Literal["clean", "oily", "rough", "smooth"] = Field(default="clean", description="质感")
    lighting_mood: str = Field(default="neutral", description="光影基调")


class ActSettings(BaseModel):
    """表演设置"""
    emotion_intensity: float = Field(default=0.5, ge=0, le=1, description="情绪强度")
    action_amplitude: float = Field(default=0.5, ge=0, le=1, description="动作幅度")
    exaggeration: float = Field(default=0.3, ge=0, le=1, description="夸张透视 (JoJo 程度)")


class CameraMotion(BaseModel):
    """镜头运动（用于微动画）"""
    type: Literal["none", "push", "pull", "pan_left", "pan_right", "tilt_up", "tilt_down", "shake"] = Field(
        default="none", description="运动类型"
    )
    intensity: float = Field(default=0.3, ge=0, le=1, description="运动强度")
    duration: float = Field(default=2.0, ge=0.5, le=10, description="持续时间（秒）")


# ===== 主模型 =====

class PanelSpec(BaseModel):
    """
    分镜规格 - Single Source of Truth
    定义分镜的所有内容、角色、气泡、生成参数
    """
    # 基本信息
    panel_id: str = Field(..., description="分镜 ID")
    order: int = Field(default=0, description="排序序号")
    title: Optional[str] = Field(default=None, description="分镜标题")
    summary: Optional[str] = Field(default=None, description="分镜摘要")
    
    # 角色与场景
    characters: List[CharacterRef] = Field(default_factory=list, description="角色列表")
    scene: SceneRef = Field(default_factory=SceneRef, description="场景设置")
    
    # 构图
    composition: CompositionSettings = Field(default_factory=CompositionSettings, description="构图设置")
    
    # 对话
    dialogue: List[DialogueLine] = Field(default_factory=list, description="对话列表")
    
    # 气泡计划
    bubble_plan: BubblePlan = Field(default_factory=BubblePlan, description="气泡计划")
    
    # 提示词
    prompt: PromptSettings = Field(default_factory=PromptSettings, description="提示词设置")
    
    # 画风/表演/镜头
    look: LookSettings = Field(default_factory=LookSettings, description="画风设置")
    act: ActSettings = Field(default_factory=ActSettings, description="表演设置")
    camera_motion: CameraMotion = Field(default_factory=CameraMotion, description="镜头运动")
    
    # 渲染级别
    render_tier: RenderTier = Field(default=RenderTier.NORMAL, description="渲染级别")
    
    # 动作描述（用于 AI 生成）
    action_description: str = Field(default="", description="动作描述（AI 生成用）")
    
    # 警告
    warnings: List[Warning] = Field(default_factory=list, description="警告列表")
    
    # 渲染信息
    render: RenderInfo = Field(default_factory=RenderInfo, description="渲染信息")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    version: int = Field(default=1, description="Schema 版本号")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "panel_id": "panel_001",
                "order": 0,
                "title": "相遇",
                "summary": "男女主在咖啡厅相遇",
                "characters": [
                    {
                        "character_id": "char_001",
                        "name": "李明",
                        "importance": "primary",
                        "position": "middle_left",
                        "scale": 1.0
                    },
                    {
                        "character_id": "char_002", 
                        "name": "小美",
                        "importance": "primary",
                        "position": "middle_right",
                        "scale": 1.0
                    }
                ],
                "scene": {
                    "scene_id": "scene_001",
                    "name": "咖啡厅",
                    "time_of_day": "day",
                    "weather": "clear",
                    "reuse_anchor": True
                },
                "composition": {
                    "shot_size": "medium",
                    "camera_angle": "eye_level",
                    "perspective_level": 0.3,
                    "subject_position": "middle_center"
                },
                "dialogue": [
                    {
                        "id": "dlg_001",
                        "type": "speech",
                        "speaker_id": "char_001",
                        "speaker_name": "李明",
                        "text": "请问这里有人吗？",
                        "emotion_tag": "nervous"
                    }
                ],
                "bubble_plan": {
                    "draft": [{"dialogue_id": "dlg_001", "candidate_regions": ["top"], "style_hint": "normal"}],
                    "final": []
                },
                "prompt": {
                    "positive": "coffee shop, two people, romantic atmosphere",
                    "negative": "text, watermark, blurry",
                    "style_strength": 0.8
                },
                "look": {
                    "style_preset": "korean_webtoon",
                    "line_hardness": 0.6,
                    "coloring_density": 0.7
                },
                "render_tier": "normal",
                "action_description": "男主角鼓起勇气走向女主角的桌子，略显紧张地询问",
                "warnings": [],
                "render": {
                    "status": "draft",
                    "qa_score": 0.0
                },
                "version": 1
            }
        }


# ===== 兼容旧版的别名 =====

# 为了向后兼容，保留旧的气泡模型
class BubbleCandidate(BaseModel):
    """气泡候选（向后兼容）"""
    id: str = Field(..., description="气泡 ID")
    text: str = Field(..., description="对话文本")
    speaker_id: Optional[str] = Field(default=None, description="说话角色 ID")
    style: str = Field(default="normal", description="气泡样式")
    position_hint: str = Field(default="auto", description="位置提示")
    font_size: int = Field(default=24, description="字体大小")
    is_vertical: bool = Field(default=False, description="是否竖排")
    x: Optional[float] = Field(default=None, description="X 坐标（百分比）")
    y: Optional[float] = Field(default=None, description="Y 坐标（百分比）")
    width: Optional[float] = Field(default=None, description="宽度（百分比）")


# 用于 API 请求的简化模型
class PanelSpecCreate(BaseModel):
    """创建分镜规格（简化版）"""
    action_description: str = Field(default="", description="动作描述")
    dialogue_text: Optional[str] = Field(default=None, description="对话文本（会自动解析）")
    shot_type: str = Field(default="medium", description="景别")
    camera_angle: str = Field(default="eye_level", description="角度")
    style_preset: str = Field(default="korean_webtoon", description="风格预设")


class PanelSpecUpdate(BaseModel):
    """更新分镜规格"""
    title: Optional[str] = None
    summary: Optional[str] = None
    action_description: Optional[str] = None
    characters: Optional[List[CharacterRef]] = None
    scene: Optional[SceneRef] = None
    composition: Optional[CompositionSettings] = None
    dialogue: Optional[List[DialogueLine]] = None
    bubble_plan: Optional[BubblePlan] = None
    prompt: Optional[PromptSettings] = None
    look: Optional[LookSettings] = None
    act: Optional[ActSettings] = None
    camera_motion: Optional[CameraMotion] = None
    render_tier: Optional[RenderTier] = None
    warnings: Optional[List[Warning]] = None
