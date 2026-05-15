"""
Bundle Manifest Schema - 章节打包清单规格 v1

定义标准化的 Bundle 目录结构和 JSON Schema
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class BundlePanelEntry(BaseModel):
    """Bundle 中单个 Panel 的清单条目"""
    index: str = Field(..., description="面板索引，如 '0001'")
    panel_id: str = Field(..., description="面板 UUID")
    path: str = Field(..., description="相对路径，如 'panels/0001'")
    
    # 产物信息
    layerpack_path: str = Field(..., description="LayerPack 相对路径")
    typeset_path: Optional[str] = Field(None, description="Typeset 相对路径")
    preview_image: str = Field(..., description="预览图路径（typeset 优先，fallback full）")
    online_preview_url: Optional[str] = Field(None, description="在线预览 URL（S3/MinIO 直链）")
    
    # 元数据
    duration_sec: Optional[float] = Field(None, description="时长（秒）")
    qa_score: Optional[float] = Field(None, description="QA 评分")
    needs_fix: bool = Field(False, description="是否需要修复")
    
    # 导出选择记录
    selected_layerpack_id: Optional[str] = Field(None, description="选用的 LayerPack ID")
    selected_typeset_id: Optional[str] = Field(None, description="选用的 Typeset ID")


class BundleQASummary(BaseModel):
    """QA 汇总信息"""
    total_panels: int = Field(..., description="总面板数")
    passed_panels: int = Field(0, description="通过面板数")
    failed_panels: int = Field(0, description="失败面板数")
    needs_fix_count: int = Field(0, description="需要修复数")
    
    min_score: Optional[float] = Field(None, description="最低分")
    max_score: Optional[float] = Field(None, description="最高分")
    avg_score: Optional[float] = Field(None, description="平均分")
    
    needs_fix_panels: List[str] = Field(default_factory=list, description="需要修复的面板索引列表")
    issues_summary: Dict[str, int] = Field(default_factory=dict, description="问题类型统计")


class BundleChapterInfo(BaseModel):
    """章节基本信息"""
    chapter_id: str
    chapter_title: str
    chapter_version: Optional[int] = Field(1, description="章节版本")
    project_id: str
    project_name: Optional[str] = None
    
    # 统计
    panel_count: int
    total_duration_sec: Optional[float] = None


class BundleProvenance(BaseModel):
    """Bundle 来源追溯"""
    generated_at: str = Field(..., description="生成时间 ISO8601")
    generated_by: Optional[str] = Field(None, description="生成者/系统")
    export_job_id: Optional[str] = Field(None, description="导出任务 ID")
    export_duration_ms: Optional[int] = Field(None, description="导出耗时毫秒")
    
    # 软件版本
    bundle_spec_version: str = Field("1.0.0", description="Bundle 规格版本")
    system_version: Optional[str] = Field(None, description="系统版本")


class BundleChapterVideo(BaseModel):
    """Phase E: reference to the D motion-comic MP4 for this chapter."""
    path: str = Field("chapter_video/compose.mp4", description="路径（相对 bundle 根目录）")
    source_compose_job_id: str = Field(..., description="产生此视频的 episode_video_compose Job ID")
    duration_sec: Optional[float] = Field(None, description="时长秒数（来自 compose Job outputs）")
    clip_count: Optional[int] = Field(None, description="参与拼接的 clip 数量")
    size_bytes: Optional[int] = Field(None, description="最终 MP4 字节数")


class BundleManifest(BaseModel):
    """
    Bundle 总清单 - manifest.json

    这是整个 Bundle 的权威入口，定义了所有资源的位置和关系
    """
    # 版本与标识
    spec_version: str = Field("1.0.0", description="Bundle 规格版本")
    bundle_id: str = Field(..., description="Bundle 唯一 ID")
    bundle_hash: Optional[str] = Field(None, description="整包 hash（可选）")

    # 章节信息
    chapter: BundleChapterInfo

    # 面板列表
    panels: List[BundlePanelEntry] = Field(default_factory=list, description="面板清单（按顺序）")

    # QA 汇总
    qa_summary: Optional[BundleQASummary] = None

    # Phase E: D motion-comic video reference (optional — present only when a
    # succeeded episode_video_compose exists for this chapter's order_index)
    chapter_video: Optional["BundleChapterVideo"] = None

    # 来源追溯
    provenance: BundleProvenance
    
    # 附加产物
    strip_path: Optional[str] = Field(None, description="长条漫路径（可选）")
    assets_path: str = Field("assets.json", description="资产锁定清单路径")
    jobs_path: str = Field("provenance/jobs.json", description="任务历史路径")
    
    # 扩展
    metadata: Dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "spec_version": "1.0.0",
                "bundle_id": "bundle-abc123",
                "chapter": {
                    "chapter_id": "ch-001",
                    "chapter_title": "第一章",
                    "project_id": "proj-001",
                    "panel_count": 25
                },
                "panels": [
                    {
                        "index": "0001",
                        "panel_id": "panel-001",
                        "path": "panels/0001",
                        "layerpack_path": "panels/0001/layerpack",
                        "preview_image": "panels/0001/typeset/typeset.png",
                        "qa_score": 0.85
                    }
                ],
                "provenance": {
                    "generated_at": "2026-01-17T10:00:00Z",
                    "bundle_spec_version": "1.0.0"
                }
            }
        }


class ChapterJsonSpec(BaseModel):
    """
    chapter.json - 章节元数据文件
    """
    chapter_id: str
    title: str
    version: int = 1
    project_id: str
    project_name: Optional[str] = None
    
    # 统计
    panel_count: int
    total_duration_sec: Optional[float] = None
    
    # 风格配置快照
    style_profile_snapshot: Optional[Dict[str, Any]] = None
    
    # 时间戳
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    exported_at: str = Field(..., description="导出时间")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PanelJsonSpec(BaseModel):
    """
    panel.json - 单个面板的元数据快照
    """
    panel_id: str
    index: str = Field(..., description="面板索引 '0001'")
    order_index: int
    
    # PanelSpec 快照
    panel_spec: Dict[str, Any] = Field(..., description="完整 PanelSpec JSON")
    
    # 导出选择
    export_selected_layerpack_id: Optional[str] = None
    export_selected_typeset_id: Optional[str] = None
    
    # 状态
    render_status: str
    qa_score: Optional[float] = None
    needs_fix: bool = False
    
    # 时间戳
    exported_at: str


class AssetsLockEntry(BaseModel):
    """资产锁定条目"""
    asset_type: str = Field(..., description="资产类型: checkpoint/lora/embedding/font/scene_anchor/face_embedding")
    asset_id: str
    name: str
    version_id: Optional[str] = None
    hash: Optional[str] = None
    storage_key: Optional[str] = None
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssetsLockSpec(BaseModel):
    """
    assets.json - 资产版本锁定
    """
    spec_version: str = Field("1.0.0")
    chapter_id: str
    exported_at: str
    
    # 模型资产
    models: List[AssetsLockEntry] = Field(default_factory=list, description="模型文件（checkpoint/vae/clip）")
    loras: List[AssetsLockEntry] = Field(default_factory=list, description="LoRA 文件")
    embeddings: List[AssetsLockEntry] = Field(default_factory=list, description="Embedding 文件")
    
    # 角色/场景资产
    face_embeddings: List[AssetsLockEntry] = Field(default_factory=list, description="人脸向量")
    scene_anchors: List[AssetsLockEntry] = Field(default_factory=list, description="场景锚点")
    
    # 字体
    fonts: List[AssetsLockEntry] = Field(default_factory=list, description="字体文件")
    
    # 汇总
    total_assets: int = 0


class JobAttemptRecord(BaseModel):
    """任务尝试记录"""
    attempt_id: str
    attempt_number: int
    status: str
    
    # 参数摘要
    seed: Optional[int] = None
    workflow_name: Optional[str] = None
    model_name: Optional[str] = None
    
    # 时间
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    
    # 输出
    outputs: Dict[str, Any] = Field(default_factory=dict)
    
    # 错误
    error: Optional[str] = None


class JobProvenanceRecord(BaseModel):
    """任务来源记录"""
    job_id: str
    job_type: str
    panel_id: Optional[str] = None
    provider: str
    
    # 时间
    created_at: str
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    
    # 参数摘要
    seed: Optional[int] = None
    workflow_name: Optional[str] = None
    workflow_hash: Optional[str] = None
    model_name: Optional[str] = None
    model_hash: Optional[str] = None
    prompt_hash: Optional[str] = None
    
    # 尝试记录
    attempts: List[JobAttemptRecord] = Field(default_factory=list)


class ProvenanceJobsSpec(BaseModel):
    """
    provenance/jobs.json - 任务运行历史
    """
    spec_version: str = Field("1.0.0")
    chapter_id: str
    exported_at: str
    
    # 任务列表
    jobs: List[JobProvenanceRecord] = Field(default_factory=list)
    
    # 统计
    total_jobs: int = 0
    total_render_jobs: int = 0
    total_typeset_jobs: int = 0
    total_duration_ms: int = 0
