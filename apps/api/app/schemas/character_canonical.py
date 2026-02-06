"""
Character Canonical Schema - 角色 Canonical 相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CanonicalStatusEnum(str, Enum):
    """Canonical 处理状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ============ Request Schemas ============

class AutoBuildRequest(BaseModel):
    """触发自动生成请求"""
    scope: str = Field("characters", description="范围: characters/scenes/all")
    force: bool = Field(False, description="强制重新生成")
    character_ids: Optional[List[str]] = Field(None, description="指定角色 ID 列表，None 表示全部")
    candidate_count: int = Field(4, description="每个角色生成的候选数量")
    style_profile: Optional[str] = Field(None, description="风格配置")


class AutoBuildResponse(BaseModel):
    """触发自动生成响应"""
    job_id: str
    message: str
    total_items: int


# ============ Status Schemas ============

class CharacterCanonicalItemStatus(BaseModel):
    """单个角色的 Canonical 状态"""
    character_id: str
    character_name: Optional[str] = None
    status: CanonicalStatusEnum
    candidates_count: int = 0
    candidate_paths: List[str] = []
    selected_path: Optional[str] = None
    selected_score: Optional[float] = None
    error: Optional[str] = None


class AutoBuildJobStatus(BaseModel):
    """自动生成 Job 状态"""
    id: str
    status: str  # queued/running/succeeded/failed
    stage: str  # collect_inputs/generate_candidates/persist_results/done
    progress: float  # 0-100
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutoBuildStatusResponse(BaseModel):
    """自动生成状态响应"""
    job: Optional[AutoBuildJobStatus] = None
    items: List[CharacterCanonicalItemStatus] = []
    total: int = 0
    completed: int = 0
    failed: int = 0


# ============ Output Schemas ============

class CharacterCanonicalOut(BaseModel):
    """CharacterCanonical 输出"""
    id: str
    chapter_id: str
    character_id: str
    character_name: Optional[str] = None
    candidate_paths: List[str] = []
    candidates_count: int = 0
    selected_path: Optional[str] = None
    selected_score: Optional[float] = None
    selection_reason: Optional[str] = None
    status: CanonicalStatusEnum
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CharacterCanonicalListOut(BaseModel):
    """CharacterCanonical 列表输出"""
    items: List[CharacterCanonicalOut]
    total: int


# ============ WS Event Schemas ============

class AssetAutobuildProgressEvent(BaseModel):
    """资产自动生成进度事件 (WS)"""
    event: str = "asset_autobuild_progress"
    job_id: str
    scope: str  # characters/scenes
    stage: str  # collect_inputs/generate_candidates/persist_results/done
    progress: float  # 0-100
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    candidate_index: Optional[int] = None
    message: Optional[str] = None
