"""
Story Artifacts - 故事生成中间产物的 Pydantic 模型
用于 StoryAgent 在对话中管理故事创作状态
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StoryGenesisPhase(str, Enum):
    """故事生成阶段"""
    INTAKE = "intake"         # 采集灵感
    BUILD = "build"           # 自主生成
    STORYBOARD = "storyboard" # 分镜生成
    COMPLETED = "completed"   # 全部完成


class ToneGuardrails(BaseModel):
    """调性约束"""
    rating: str = Field(default="teen", description="Rating: all_ages / teen / adult")
    comedy_level: int = Field(default=3, ge=1, le=5, description="Comedy level 1-5")
    violence_level: int = Field(default=2, ge=1, le=5, description="Violence level 1-5")


class CreativeBrief(BaseModel):
    """创意简报 — 从 INTAKE 阶段提取"""
    title: str = Field(default="", description="Working title")
    genre: str = Field(default="", description="Primary genre")
    comparisons: List[str] = Field(default_factory=list, description="2 comparison works")
    anti_comparison: str = Field(default="", description="Anti-comparison work")
    logline: str = Field(default="", description="One-sentence logline")
    theme_question: str = Field(default="", description="Core theme question")
    story_engine: str = Field(default="", description="What creates new problems each episode")
    tone: ToneGuardrails = Field(default_factory=ToneGuardrails)
    setting: str = Field(default="", description="Location and time period")
    visual_keywords: List[str] = Field(default_factory=list, description="5-10 visual style keywords")
    ending_stakes: str = Field(default="", description="Irreversible change by the end")


class RelationshipAxis(BaseModel):
    """角色关系轴"""
    target_character: str = ""
    trust: int = Field(default=3, ge=1, le=5)
    respect: int = Field(default=3, ge=1, le=5)
    dependency: int = Field(default=3, ge=1, le=5)
    intimacy: int = Field(default=3, ge=1, le=5)
    moral_alignment: int = Field(default=3, ge=1, le=5)


class CharacterProfile(BaseModel):
    """角色档案"""
    name: str = ""
    age: str = ""
    age_range: str = Field(default="", description="Pipeline-aligned: 20s / teen / middle-aged / elderly")
    gender: str = ""
    role: str = Field(default="supporting", description="protagonist / antagonist / supporting / minor")

    # Visual (AI image generation optimized)
    face_description: str = ""
    hair_description: str = ""
    build: str = ""
    distinguishing_features: str = ""
    default_outfit: str = ""
    outfit_variants: List[str] = Field(default_factory=list)
    visual_tags: List[str] = Field(default_factory=list, description="Comma-separated tags for image gen")

    # Pipeline-aligned fields (maps to CharacterIR)
    appearance_keywords: List[str] = Field(
        default_factory=list,
        description="外观关键词列表 (maps to CharacterIR.appearance_keywords): e.g. ['black hair', 'brown eyes', 'slim']",
    )
    personality_keywords: List[str] = Field(
        default_factory=list,
        description="性格关键词列表 (maps to CharacterIR.personality_keywords): e.g. ['内向', '温柔']",
    )
    importance: str = Field(default="supporting", description="protagonist / supporting / minor")

    # Personality
    core_traits: List[str] = Field(default_factory=list)
    strength: str = ""
    flaw: str = ""
    speech_pattern: str = ""

    # Power Stack psychology
    want: str = Field(default="", description="External goal")
    need: str = Field(default="", description="Internal growth")
    lie: str = Field(default="", description="Lie they believe")
    ghost: str = Field(default="", description="Past wound")

    # Relationships
    relationships: List[RelationshipAxis] = Field(default_factory=list)
    backstory: str = ""


class SceneBeat(BaseModel):
    """场景节拍"""
    beat_index: int = 0
    title: str = ""
    goal: str = Field(default="", description="Scene goal")
    obstacle: str = Field(default="", description="Scene obstacle")
    turn: str = Field(default="", description="Scene turn / surprise")
    cost: str = Field(default="", description="What it costs the character")
    action: str = ""
    dialogue: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of {speaker, text, direction} dicts",
    )

    # Pipeline-aligned (maps to BeatIR)
    source_quote: str = Field(
        default="",
        description="Generated text serving as 'original' for pipeline source tracing (maps to BeatIR.source_quote)",
    )
    emotion_shift: str = Field(
        default="",
        description="Emotion arc: 'start_emotion → end_emotion' (maps to BeatIR.emotion_shift)",
    )
    tension_level: int = Field(default=5, ge=1, le=10, description="1=calm, 10=climax")


class ScreenplayScene(BaseModel):
    """剧本场景"""
    scene_index: int = 0
    scene_name: str = ""
    location: str = ""
    time_of_day: str = Field(default="day", description="dawn/morning/noon/afternoon/dusk/night")
    weather_mood: str = Field(default="clear", description="clear/cloudy/rainy/stormy/snowy/foggy")
    characters_present: List[str] = Field(default_factory=list)
    visual_atmosphere: str = ""
    beats: List[SceneBeat] = Field(default_factory=list)

    # Camera / visual hints (pipeline-aligned enums)
    suggested_shot_types: List[str] = Field(
        default_factory=list,
        description="Pipeline enums: ECU/CU/MCU/MS/MLS/LS/WS/EWS/OTS/POV",
    )
    lighting: str = ""
    key_visual: str = ""

    # Pipeline emotion/pacing fields
    emotion_label: str = Field(
        default="neutral",
        description="tense/calm/joyful/sad/angry/fearful/hopeful/melancholic/dramatic/neutral",
    )
    pacing: str = Field(
        default="moderate",
        description="slow (4-8s) / moderate (2.5-4s) / fast (1.5-2.5s) / climax (3-6s)",
    )


class Screenplay(BaseModel):
    """完整剧本"""
    title: str = ""
    episode_number: int = 1
    genre: str = ""
    estimated_panels: int = 0
    scenes: List[ScreenplayScene] = Field(default_factory=list)
    summary_table: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Scene summary: [{scene, location, characters, key_event, panels}]",
    )


class IntakeProgress(BaseModel):
    """INTAKE 阶段进度追踪"""
    questions_asked: int = 0
    questions_total: int = 8
    collected_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(
        default_factory=lambda: [
            "genre", "protagonist_flaw", "core_relationship",
            "story_engine", "theme_question", "tone",
            "visual_style", "ending_stakes",
        ]
    )


class StoryGenesisState(BaseModel):
    """故事生成全局状态 — 存储在对话上下文中"""
    phase: StoryGenesisPhase = StoryGenesisPhase.INTAKE
    intake_progress: IntakeProgress = Field(default_factory=IntakeProgress)
    creative_brief: Optional[CreativeBrief] = None
    characters: List[CharacterProfile] = Field(default_factory=list)
    screenplay: Optional[Screenplay] = None
    storyboard_draft_id: Optional[str] = None

    # Asset tracking — maps "char:<name>" / "scene:<name>" → Asset DB ID
    asset_ids: Dict[str, str] = Field(
        default_factory=dict,
        description="Persisted Asset DB IDs: {'char:名前': 'uuid', 'scene:旧書店': 'uuid'}",
    )

    # Pipeline integration
    director_preset: str = Field(
        default="default",
        description="Selected DirectorProfile: default / romance / thriller / contemplative",
    )

    # 用于对话管理
    conversation_summary: str = ""
    language: str = Field(default="auto", description="auto / zh / en — detected from user messages")
