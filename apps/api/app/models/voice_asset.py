"""
Voice Asset Models - 声音资产（配音智能体、音乐）
"""
from sqlalchemy import Column, String, Text, Float, Boolean, ForeignKey, JSON, Enum as SQLEnum
from app.models.base import Base, TimestampMixin
from sqlalchemy.orm import relationship, backref
import uuid
import enum


class VoiceAgentStatus(str, enum.Enum):
    """配音智能体状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"


class VoiceAgent(Base, TimestampMixin):
    """AI 配音智能体 - 绑定到角色资产"""
    __tablename__ = "voice_agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    # 必填，关联的角色资产
    character_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)

    # 智能体名称（默认：{角色名}的配音）
    name = Column(String(100), nullable=False)

    # 豆包音色 ID
    voice_id = Column(String(50), nullable=False)

    # TTS 提供商
    provider = Column(String(50), default="doubao")

    # 音色配置（speed, pitch, volume）
    voice_config = Column(JSON, nullable=False, default=dict)

    # 示例音频
    sample_audio_url = Column(String(512), nullable=True)

    # 是否为角色默认配音
    is_default = Column(Boolean, default=False)

    # 状态
    status = Column(String(50), default="active")

    # 关系
    project = relationship("Project", backref=backref("voice_agents", cascade="all, delete-orphan"))
    character_asset = relationship("Asset", backref=backref("voice_agents", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<VoiceAgent {self.id}: {self.name}>"


class MusicStatus(str, enum.Enum):
    """音乐资产状态"""
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class MusicProvider(str, enum.Enum):
    """音乐生成提供商"""
    SUNO_COMFYUI = "suno_via_comfyui"
    MANUAL = "manual"


class MusicAsset(Base, TimestampMixin):
    """音乐资产"""
    __tablename__ = "music_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    # 音乐名称
    name = Column(String(100), nullable=False)

    # 风格类型
    genre = Column(String(50), nullable=True)

    # 情绪/氛围
    mood = Column(String(50), nullable=True)

    # 时长（秒）
    duration_sec = Column(Float, nullable=True)

    # 音频文件 URL
    audio_url = Column(String(512), nullable=True)

    # 生成提供商
    provider = Column(String(50), default="manual")

    # 生成提示词
    generation_prompt = Column(Text, nullable=True)

    # 生成参数
    generation_params = Column(JSON, nullable=True)

    # ComfyUI 工作流/任务 ID
    workflow_id = Column(String(100), nullable=True)
    job_id = Column(String(100), nullable=True)

    # 状态
    status = Column(String(50), default="ready")

    # 缩略图（封面）
    thumbnail_url = Column(String(512), nullable=True)

    # 关系
    project = relationship("Project", backref=backref("music_assets", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<MusicAsset {self.id}: {self.name}>"
