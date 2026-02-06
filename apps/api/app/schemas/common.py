"""
Common schemas - 通用响应模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Generic, TypeVar, Any, Dict
from datetime import datetime

T = TypeVar('T')


class StatusResponse(BaseModel):
    """状态响应"""
    status: str = Field(..., description="状态")
    message: str = Field(default="", description="消息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# ===== Project Schemas =====

class ProjectBase(BaseModel):
    """项目基础"""
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(default=None, description="项目描述")


class ProjectCreate(ProjectBase):
    """创建项目"""
    pass


class ProjectUpdate(BaseModel):
    """更新项目"""
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    cover_image: Optional[str] = None
    is_archived: Optional[bool] = None


class ProjectResponse(ProjectBase):
    """项目响应"""
    id: str
    cover_image: Optional[str] = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    chapter_count: int = 0
    
    class Config:
        from_attributes = True


# ===== Chapter Schemas =====

class ChapterBase(BaseModel):
    """章节基础"""
    title: str = Field(..., min_length=1, max_length=255, description="章节标题")
    description: Optional[str] = Field(default=None, description="章节描述")


class ChapterCreate(ChapterBase):
    """创建章节"""
    project_id: str = Field(..., description="所属项目 ID")
    order_index: int = Field(default=0, description="排序序号")


class ChapterUpdate(BaseModel):
    """更新章节"""
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    order_index: Optional[int] = None


class ChapterResponse(ChapterBase):
    """章节响应"""
    id: str
    project_id: str
    order_index: int
    layout_json: Dict[str, Any] = {}
    export_status: str = "draft"
    exported_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    panel_count: int = 0
    
    class Config:
        from_attributes = True


# ===== Panel Schemas =====

class PanelBase(BaseModel):
    """分镜基础"""
    title: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None


class PanelCreate(BaseModel):
    """创建分镜"""
    chapter_id: str = Field(..., description="所属章节 ID")
    title: Optional[str] = None
    summary: Optional[str] = None
    spec_json: Dict[str, Any] = Field(default_factory=dict)
    order_index: Optional[int] = None


class PanelUpdate(BaseModel):
    """更新分镜"""
    title: Optional[str] = None
    summary: Optional[str] = None
    order_index: Optional[int] = None
    render_tier: Optional[str] = None


class PanelSpecUpdate(BaseModel):
    """更新分镜规格"""
    spec_json: Dict[str, Any] = Field(..., description="PanelSpec JSON")


class PanelResponse(PanelBase):
    """分镜响应"""
    id: str
    chapter_id: str
    order_index: int
    spec_json: Dict[str, Any] = {}
    render_status: str = "draft"
    active_layer_pack_id: Optional[str] = None
    preview_url: Optional[str] = None
    typeset_status: str = "pending"
    typeset_image_url: Optional[str] = None
    qa_score: float = 0.0
    needs_manual_fix: str = "false"
    warning_count: int = 0
    error_count: int = 0
    render_tier: str = "normal"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ===== Asset Schemas =====

class AssetBase(BaseModel):
    """资产基础"""
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., description="资产类型: character/scene/style/bubble/effect")
    description: Optional[str] = None


class AssetCreate(AssetBase):
    """创建资产"""
    project_id: str
    data_json: Dict[str, Any] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    """更新资产"""
    name: Optional[str] = None
    description: Optional[str] = None
    data_json: Optional[Dict[str, Any]] = None
    thumbnail_url: Optional[str] = None
    status: Optional[str] = None


class AssetResponse(AssetBase):
    """资产响应"""
    id: str
    project_id: str
    thumbnail_url: Optional[str] = None
    data_json: Dict[str, Any] = {}
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ===== RenderJob Schemas =====

class RenderJobCreate(BaseModel):
    """创建渲染任务"""
    panel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    job_type: str = Field(default="layer_generation")
    input_params: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class RenderJobResponse(BaseModel):
    """渲染任务响应"""
    id: str
    panel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    job_type: str
    status: str
    progress: float = 0
    current_step: Optional[str] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ===== Studio Aggregated Response =====

class StudioCharacterSummary(BaseModel):
    """工作台角色摘要"""
    id: str
    name: str
    thumbnail_url: Optional[str] = None
    face_embedding_status: str = "none"  # none/pending/ready
    reference_count: int = 0


class StudioSceneSummary(BaseModel):
    """工作台场景摘要"""
    id: str
    name: str
    thumbnail_url: Optional[str] = None
    anchor_status: str = "none"  # none/pending/ready
    control_maps_ready: bool = False


class StudioPanelSummary(BaseModel):
    """工作台分镜摘要"""
    id: str
    order_index: int
    title: Optional[str] = None
    summary: Optional[str] = None
    preview_url: Optional[str] = None
    render_status: str = "draft"
    typeset_status: str = "pending"
    qa_score: float = 0.0
    warning_count: int = 0
    error_count: int = 0
    render_tier: str = "normal"
    dialogue_preview: Optional[str] = None  # 第一句对话预览
    character_ids: List[str] = []
    scene_id: Optional[str] = None
    # 结构化字段 (从 spec_json 提取)
    shot_type: Optional[str] = None
    camera_move: Optional[str] = None
    camera_angle: Optional[str] = None
    duration_sec: Optional[float] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    mood: Optional[str] = None
    emotion: Optional[str] = None
    action_description: Optional[str] = None


class StudioJobSummary(BaseModel):
    """工作台任务摘要"""
    id: str
    panel_id: Optional[str] = None
    job_type: str
    status: str
    progress: float = 0
    current_step: Optional[str] = None


class StudioWarning(BaseModel):
    """工作台警告"""
    type: str
    severity: str  # info/warning/error
    message: str
    panel_id: Optional[str] = None
    asset_id: Optional[str] = None
    auto_fixable: bool = False


class ChapterStudioResponse(BaseModel):
    """
    章节工作台聚合响应
    GET /chapters/{chapter_id}/studio
    包含前端渲染章节工作台所需的所有数据
    """
    # 基本信息
    chapter: ChapterResponse
    layout: Dict[str, Any]  # ChapterLayout JSON
    
    # 分镜列表（按顺序）
    panels: List[StudioPanelSummary]
    panels_by_id: Dict[str, PanelResponse]  # 完整分镜数据
    
    # 资产
    characters: List[StudioCharacterSummary]
    scenes: List[StudioSceneSummary]
    styles: List[AssetResponse]
    bubble_styles: List[AssetResponse]
    
    # 任务状态
    active_jobs: List[StudioJobSummary]
    
    # 警告汇总
    warnings: List[StudioWarning]
    
    # 统计
    stats: Dict[str, Any] = Field(default_factory=lambda: {
        "total_panels": 0,
        "rendered_panels": 0,
        "failed_panels": 0,
        "pending_jobs": 0,
        "avg_qa_score": 0.0
    })


# ===== Script & Storyboard =====

class ScriptSubmitRequest(BaseModel):
    """提交剧本请求"""
    script_text: str = Field(..., min_length=1, description="剧本文本")
    style_hint: str = Field(default="korean_webtoon", description="风格提示")
    auto_storyboard: bool = Field(default=True, description="是否自动分镜")
    context: Optional[Dict[str, Any]] = None


class ScriptSubmitResponse(BaseModel):
    """提交剧本响应"""
    success: bool
    chapter_id: str
    panels_created: int
    characters_detected: List[str]
    scenes_detected: List[str]
    warnings: List[StudioWarning]


# ===== Render Request =====

class RenderRequest(BaseModel):
    """渲染请求"""
    panel_ids: Optional[List[str]] = Field(default=None, description="指定分镜 ID，为空则渲染全部")
    force_regenerate: bool = Field(default=False, description="强制重新生成")
    priority: int = Field(default=0, description="优先级")


class RenderResponse(BaseModel):
    """渲染响应"""
    success: bool
    jobs_created: int
    job_ids: List[str]


# ===== Export Request =====

class ExportStripRequest(BaseModel):
    """导出长条漫请求"""
    include_typeset: bool = Field(default=True, description="是否包含嵌字")
    format: str = Field(default="png", description="格式: png/jpg/webp")
    quality: int = Field(default=95, ge=1, le=100)


class ExportResponse(BaseModel):
    """导出响应"""
    success: bool
    job_id: str
    status: str


# ===== WebSocket Events =====

class WSJobUpdate(BaseModel):
    """WebSocket 任务更新事件"""
    event: str = "job_status_update"
    job_id: str
    panel_id: Optional[str] = None
    status: str
    progress: float = 0
    current_step: Optional[str] = None
    result_urls: Optional[Dict[str, str]] = None
    error: Optional[str] = None


class WSPanelUpdate(BaseModel):
    """WebSocket 分镜更新事件"""
    event: str = "panel_update"
    panel_id: str
    render_status: str
    preview_url: Optional[str] = None
    qa_score: float = 0.0
