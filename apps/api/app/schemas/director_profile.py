"""
DirectorProfile - 导演风格约束

这是 LLM Plan 阶段的约束输入，定义镜头语言、节奏偏好、画风约束。
让 LLM 按照特定的"导演风格"生成分镜。
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from enum import Enum


# ============ 镜头类型枚举 ============

class ShotType(str, Enum):
    """镜头类型枚举"""
    ECU = "ECU"  # Extreme Close-Up - 极特写 (眼睛/细节/物品特写)
    CU = "CU"    # Close-Up - 特写 (面部表情)
    MCU = "MCU"  # Medium Close-Up - 中特写 (头肩)
    MS = "MS"    # Medium Shot - 中景 (腰部以上)
    MLS = "MLS"  # Medium Long Shot - 中远景 (膝盖以上)
    LS = "LS"    # Long Shot - 远景 (全身)
    WS = "WS"    # Wide Shot - 大远景 (人物+环境)
    EWS = "EWS"  # Extreme Wide Shot - 极大远景 (建立镜头)
    OTS = "OTS"  # Over-the-Shoulder - 过肩镜头
    POV = "POV"  # Point of View - 主观视角


class CameraMove(str, Enum):
    """运镜类型枚举"""
    STATIC = "static"          # 静止
    PUSH_IN = "push_in"        # 推 (靠近主体)
    PULL_OUT = "pull_out"      # 拉 (远离主体)
    PAN_LEFT = "pan_left"      # 左摇
    PAN_RIGHT = "pan_right"    # 右摇
    TILT_UP = "tilt_up"        # 上摇
    TILT_DOWN = "tilt_down"    # 下摇
    DOLLY = "dolly"            # 移动 (轨道)
    TRACKING = "tracking"      # 跟踪
    HANDHELD = "handheld"      # 手持 (微晃)
    ZOOM_IN = "zoom_in"        # 变焦推
    ZOOM_OUT = "zoom_out"      # 变焦拉
    CRANE = "crane"            # 摇臂


class CameraAngle(str, Enum):
    """机位角度枚举"""
    EYE_LEVEL = "eye_level"    # 平视
    HIGH = "high"              # 俯拍
    LOW = "low"                # 仰拍
    BIRDS_EYE = "birds_eye"    # 鸟瞰
    WORMS_EYE = "worms_eye"    # 蚂蚁视角
    DUTCH = "dutch"            # 荷兰角 (倾斜)


# ============ 镜头语法表 ============

class EmotionShotRule(BaseModel):
    """情绪 → 镜头映射规则"""
    emotion_trigger: str  # 触发情绪
    recommended_shot: ShotType
    recommended_move: CameraMove
    recommended_angle: CameraAngle = CameraAngle.EYE_LEVEL
    duration_hint: float = 3.0  # 建议时长
    rationale: str = ""  # 使用理由


class ShotGrammar(BaseModel):
    """
    镜头语法表
    
    定义镜头类型的权重分布和情绪→镜头映射规则
    """
    
    # 镜头类型权重分布 (总和应为 1.0)
    shot_type_weights: Dict[str, float] = Field(
        default={
            "ECU": 0.05,   # 极特写 - 用于关键情绪细节
            "CU": 0.20,    # 特写 - 面部表情
            "MCU": 0.15,   # 中特写 - 对话常用
            "MS": 0.30,    # 中景 - 最常用
            "MLS": 0.10,   # 中远景
            "LS": 0.10,    # 远景
            "WS": 0.08,    # 大远景
            "EWS": 0.02,   # 极大远景 - 建立镜头
        },
        description="镜头类型目标权重分布"
    )
    
    # 运镜类型可用列表
    allowed_camera_moves: List[CameraMove] = Field(
        default=[
            CameraMove.STATIC, CameraMove.PUSH_IN, CameraMove.PULL_OUT,
            CameraMove.PAN_LEFT, CameraMove.PAN_RIGHT, CameraMove.HANDHELD
        ]
    )
    
    # 情绪 → 镜头映射规则
    emotion_shot_rules: List[EmotionShotRule] = Field(
        default_factory=lambda: [
            EmotionShotRule(
                emotion_trigger="tension_rising",
                recommended_shot=ShotType.CU,
                recommended_move=CameraMove.PUSH_IN,
                duration_hint=2.5,
                rationale="紧张升温时用特写+推镜强化压迫感"
            ),
            EmotionShotRule(
                emotion_trigger="awkward_pause",
                recommended_shot=ShotType.MS,
                recommended_move=CameraMove.STATIC,
                duration_hint=3.5,
                rationale="尴尬沉默用中景静止，留出空间感"
            ),
            EmotionShotRule(
                emotion_trigger="revelation",
                recommended_shot=ShotType.ECU,
                recommended_move=CameraMove.STATIC,
                duration_hint=2.0,
                rationale="揭示时刻用极特写捕捉反应"
            ),
            EmotionShotRule(
                emotion_trigger="establishing",
                recommended_shot=ShotType.WS,
                recommended_move=CameraMove.PAN_RIGHT,
                duration_hint=4.0,
                rationale="建立场景用大远景+摇镜"
            ),
            EmotionShotRule(
                emotion_trigger="intimacy",
                recommended_shot=ShotType.CU,
                recommended_move=CameraMove.STATIC,
                duration_hint=3.0,
                rationale="亲密时刻用特写静止，聚焦情感"
            ),
            EmotionShotRule(
                emotion_trigger="sadness",
                recommended_shot=ShotType.MCU,
                recommended_move=CameraMove.PULL_OUT,
                duration_hint=4.0,
                rationale="悲伤用中特写+拉镜，表达孤独感"
            ),
            EmotionShotRule(
                emotion_trigger="surprise",
                recommended_shot=ShotType.CU,
                recommended_move=CameraMove.STATIC,
                duration_hint=1.5,
                rationale="惊讶用快速特写捕捉表情"
            ),
            EmotionShotRule(
                emotion_trigger="romance",
                recommended_shot=ShotType.MCU,
                recommended_move=CameraMove.PUSH_IN,
                duration_hint=3.5,
                rationale="浪漫时刻用中特写慢推"
            ),
        ]
    )
    
    def get_rule_for_emotion(self, emotion: str) -> Optional[EmotionShotRule]:
        """根据情绪获取镜头规则"""
        emotion_lower = emotion.lower()
        for rule in self.emotion_shot_rules:
            if rule.emotion_trigger.lower() in emotion_lower or emotion_lower in rule.emotion_trigger.lower():
                return rule
        return None


# ============ 导演风格约束 ============

class DirectorProfile(BaseModel):
    """
    导演风格约束
    
    定义整体节奏、镜头偏好、画风约束
    """
    
    # ===== 身份 =====
    name: str = "默认导演"
    style_description: str = "韩式条漫风格，温柔细腻，注重情感表达"
    
    # ===== 节奏参数 =====
    shots_per_minute: float = Field(
        default=8.0,
        ge=4.0, le=20.0,
        description="每分钟镜头数 (4-20)"
    )
    avg_shot_duration: float = Field(
        default=3.5,
        ge=1.5, le=8.0,
        description="平均镜头时长（秒）"
    )
    min_shot_duration: float = Field(
        default=1.5,
        ge=0.5, le=3.0,
        description="最短镜头时长"
    )
    max_shot_duration: float = Field(
        default=8.0,
        ge=5.0, le=15.0,
        description="最长镜头时长"
    )
    
    # ===== 镜头偏好 =====
    shot_grammar: ShotGrammar = Field(default_factory=ShotGrammar)
    
    close_up_ratio: float = Field(
        default=0.40,
        ge=0.1, le=0.8,
        description="近景镜头占比 (CU+MCU)"
    )
    movement_ratio: float = Field(
        default=0.20,
        ge=0.0, le=0.6,
        description="运动镜头占比 (非 static)"
    )
    
    # ===== 画风偏好 =====
    style_preset: Literal[
        "korean_webtoon", "manga", "manhwa", "comic", "realistic", "anime"
    ] = "korean_webtoon"
    
    lighting_mood: Literal[
        "soft", "dramatic", "natural", "dim", "bright", "golden_hour"
    ] = "soft"
    
    color_palette: Literal[
        "warm", "cool", "muted", "vibrant", "pastel", "monochrome"
    ] = "warm"
    
    # ===== 情绪曲线 =====
    emotion_keywords: List[str] = Field(
        default_factory=lambda: ["温柔", "细腻", "克制"],
        description="整体情绪关键词"
    )
    
    pacing_style: Literal[
        "slow_burn",      # 慢热型 - 细腻铺垫
        "dynamic",        # 动态型 - 节奏变化大
        "contemplative",  # 沉思型 - 大量留白
        "thriller",       # 悬疑型 - 紧凑紧张
        "comedy",         # 喜剧型 - 轻快节奏
    ] = "slow_burn"
    
    # ===== 特殊约束 =====
    
    # 镜头变化约束
    min_shot_changes_per_minute: int = Field(
        default=4,
        description="每分钟最少镜头变化次数"
    )
    
    # 情绪拐点约束
    min_emotion_beats_per_minute: int = Field(
        default=2,
        description="每分钟最少情绪拐点"
    )
    
    # 对话场景偏好
    dialogue_shot_preference: Literal[
        "shot_reverse",   # 正反打
        "two_shot",       # 双人镜头
        "ots",            # 过肩
        "singles",        # 单人特写
    ] = "shot_reverse"
    
    def to_prompt_context(self) -> str:
        """转换为 LLM 提示词上下文"""
        return f"""## 导演风格约束

**风格**: {self.style_description}
**节奏**: 每分钟 {self.shots_per_minute} 个镜头，平均时长 {self.avg_shot_duration}s
**镜头偏好**: 近景占比 {self.close_up_ratio*100:.0f}%，运动镜头 {self.movement_ratio*100:.0f}%
**画风**: {self.style_preset}，{self.lighting_mood} 光线，{self.color_palette} 色调
**情绪**: {', '.join(self.emotion_keywords)}，{self.pacing_style} 节奏
**约束**: 每分钟至少 {self.min_shot_changes_per_minute} 次镜头变化，{self.min_emotion_beats_per_minute} 个情绪拐点
"""


# ============ 预设导演风格 ============

def get_default_director() -> DirectorProfile:
    """获取默认导演风格"""
    return DirectorProfile()


def get_romance_director() -> DirectorProfile:
    """浪漫韩剧风格导演"""
    return DirectorProfile(
        name="浪漫韩剧导演",
        style_description="唯美浪漫，细腻情感，大量特写和慢镜头",
        shots_per_minute=6.0,
        avg_shot_duration=4.5,
        close_up_ratio=0.55,
        movement_ratio=0.15,
        lighting_mood="soft",
        color_palette="warm",
        emotion_keywords=["浪漫", "心动", "温柔", "甜蜜"],
        pacing_style="slow_burn",
    )


def get_thriller_director() -> DirectorProfile:
    """悬疑惊悚风格导演"""
    return DirectorProfile(
        name="悬疑导演",
        style_description="紧张压迫，快速剪辑，大量荷兰角和手持镜头",
        shots_per_minute=12.0,
        avg_shot_duration=2.5,
        close_up_ratio=0.45,
        movement_ratio=0.40,
        lighting_mood="dramatic",
        color_palette="cool",
        emotion_keywords=["紧张", "悬疑", "不安", "压迫"],
        pacing_style="thriller",
    )


def get_contemplative_director() -> DirectorProfile:
    """文艺沉思风格导演"""
    return DirectorProfile(
        name="文艺导演",
        style_description="大量留白，长镜头，环境与情绪融合",
        shots_per_minute=4.0,
        avg_shot_duration=6.0,
        close_up_ratio=0.25,
        movement_ratio=0.10,
        lighting_mood="natural",
        color_palette="muted",
        emotion_keywords=["沉思", "孤独", "释然", "诗意"],
        pacing_style="contemplative",
    )
