"""
Script IR - 剧本结构化中间表示

这是 LLM 分镜流水线的核心数据结构，将剧本文本转化为可计算的结构。
用于 3 阶段流水线：Parse → Plan → Bind
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple, Literal
from datetime import datetime
import hashlib


# ============ 角色定义 ============

class CharacterRelationship(BaseModel):
    """角色关系"""
    target_id: str  # 关系目标角色 ID
    relation_type: str  # 关系类型: friend/rival/lover/family/colleague
    description: str  # 关系描述


class CharacterIR(BaseModel):
    """角色定义 (IR = Intermediate Representation)"""
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list, description="别名列表")
    
    # 基本属性
    gender: Optional[Literal["male", "female", "other", "unknown"]] = None
    age_range: Optional[str] = None  # "20s", "teen", "middle-aged", "elderly"
    
    # 外观关键词（用于 AI 图像生成）
    appearance_keywords: List[str] = Field(
        default_factory=list,
        description="外观关键词: 发型、发色、眼睛、服装风格等"
    )
    
    # 性格关键词
    personality_keywords: List[str] = Field(
        default_factory=list,
        description="性格关键词: 内向、开朗、冷静等"
    )
    
    # 角色关系
    relationships: List[CharacterRelationship] = Field(default_factory=list)
    
    # 在剧本中的重要性
    importance: Literal["protagonist", "supporting", "minor"] = "supporting"
    
    # 来源标注
    first_appearance_beat: Optional[str] = None  # 首次出现的 beat ID


# ============ 场景定义 ============

class SceneIR(BaseModel):
    """场景定义"""
    id: str
    name: str  # 场景名称 (如 "旧书店")
    
    # 场景类型
    location_type: Literal["indoor", "outdoor", "transitional"] = "indoor"
    location_category: str = ""  # 细分类型: bookstore, cafe, street, home
    
    # 时间与天气
    time_period: Literal[
        "dawn", "morning", "noon", "afternoon", "dusk", "night"
    ] = "day"
    weather: Literal[
        "clear", "cloudy", "overcast", "rainy", "stormy", "snowy", "foggy"
    ] = "clear"
    
    # 氛围
    atmosphere_keywords: List[str] = Field(
        default_factory=list,
        description="氛围关键词: 温馨、紧张、浪漫、阴郁等"
    )
    lighting: str = "natural"  # natural, warm, cold, dim, dramatic
    
    # 关键道具和元素
    props: List[str] = Field(
        default_factory=list,
        description="场景中的关键道具"
    )
    
    # 场景描述（用于 AI 图像生成）
    visual_description: str = ""


# ============ 剧情节拍 ============

class BeatIR(BaseModel):
    """
    剧情节拍 - 按事件切分，不按段落切
    
    每个 beat 代表一个"可视化的故事单元"
    """
    id: str
    index: int  # 节拍序号 (0-based)
    
    # ===== 5W1H =====
    who: List[str] = Field(
        description="参与角色 ID 列表"
    )
    where: str = Field(
        description="场景 ID"
    )
    when: str = Field(
        description="时间描述（相对于故事时间线）"
    )
    what_happens: str = Field(
        description="发生什么 - 动作/事件描述（50-100字）"
    )
    why_intent: str = Field(
        description="为什么/意图 - 这个动作的目的或潜台词"
    )
    emotion_shift: str = Field(
        description="情绪变化，格式: '起始情绪 → 结束情绪'"
    )
    
    # ===== 原文对齐（防幻觉）=====
    source_quote: str = Field(
        description="原文摘录（支撑这个 beat 的原文片段）"
    )
    source_span: Optional[Tuple[int, int]] = Field(
        default=None,
        description="原文字符位置 [start, end]"
    )
    
    # ===== 节拍元数据 =====
    tension_level: int = Field(
        default=5,
        ge=1, le=10,
        description="张力值 1-10 (1=平静, 10=高潮)"
    )
    pacing: Literal["slow", "normal", "fast"] = "normal"
    
    # 对话内容（如果有）
    dialogue: Optional[str] = None
    dialogue_speaker: Optional[str] = None  # 说话人角色 ID
    
    # 预估时长（秒）
    suggested_duration: float = Field(
        default=4.0,
        ge=1.0, le=15.0,
        description="建议时长（秒）"
    )
    
    # 镜头数量建议
    suggested_panel_count: int = Field(
        default=1,
        ge=1, le=3,
        description="建议分镜数量 (1-3)"
    )


# ============ 整体结构 ============

class ScriptIR(BaseModel):
    """
    剧本结构化表示 (Script Intermediate Representation)
    
    这是 LLM Parse 阶段的输出，也是 Plan 阶段的输入
    """
    # 版本标识
    version: str = "1.0"
    script_hash: str = Field(
        description="原文 MD5 hash，用于版本对比和缓存"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 核心元素
    characters: List[CharacterIR] = Field(default_factory=list)
    scenes: List[SceneIR] = Field(default_factory=list)
    beats: List[BeatIR] = Field(default_factory=list)
    
    # ===== 整体分析 =====
    
    # 时长预估
    total_duration_hint: float = Field(
        default=60.0,
        description="预估总时长（秒）"
    )
    
    # 情感曲线
    emotional_arc: str = Field(
        default="",
        description="情感曲线描述（如：平静→心动→克制→释然）"
    )
    
    # 关键转折点
    key_moments: List[str] = Field(
        default_factory=list,
        description="关键转折点的 beat IDs"
    )
    
    # 主题标签
    themes: List[str] = Field(
        default_factory=list,
        description="主题标签（如：暗恋、青春、遗憾）"
    )
    
    # ===== 验证 =====
    
    def validate_integrity(self) -> List[str]:
        """验证 IR 完整性"""
        issues = []
        
        char_ids = {c.id for c in self.characters}
        scene_ids = {s.id for s in self.scenes}
        
        for beat in self.beats:
            # 检查角色引用
            for who in beat.who:
                if who not in char_ids:
                    issues.append(f"Beat {beat.id}: 引用了未定义的角色 {who}")
            
            # 检查场景引用
            if beat.where not in scene_ids:
                issues.append(f"Beat {beat.id}: 引用了未定义的场景 {beat.where}")
            
            # 检查原文摘录
            if not beat.source_quote:
                issues.append(f"Beat {beat.id}: 缺少原文摘录 (source_quote)")
        
        return issues
    
    @staticmethod
    def compute_hash(script_text: str) -> str:
        """计算剧本文本的 hash"""
        return hashlib.md5(script_text.encode('utf-8')).hexdigest()


# ============ 辅助函数 ============

def create_empty_script_ir(script_text: str) -> ScriptIR:
    """创建空的 ScriptIR 结构"""
    return ScriptIR(
        script_hash=ScriptIR.compute_hash(script_text),
        characters=[],
        scenes=[],
        beats=[],
    )
