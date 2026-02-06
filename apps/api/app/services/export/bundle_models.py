"""
Bundle Models - 内部数据结构

用于 BundleBuilder 流水线的中间数据结构
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class PanelSnapshot:
    """面板快照 - 导出所需的最小信息"""
    panel_id: str
    index_str: str  # "0001", "0002"...
    order_index: int
    
    # PanelSpec 快照（JSON）
    panel_spec_json: Dict[str, Any]
    
    # 选中的产物 ID
    selected_layerpack_id: Optional[str] = None
    selected_typeset_id: Optional[str] = None
    
    # 状态
    render_status: str = "unknown"
    qa_score: Optional[float] = None
    needs_fix: bool = False
    
    # 时长
    duration_sec: Optional[float] = None


@dataclass
class ChapterSnapshot:
    """章节快照 - 导出整章所需信息"""
    chapter_id: str
    project_id: str
    
    title: str
    version: int = 1
    
    # 面板列表（按顺序）
    panels: List[PanelSnapshot] = field(default_factory=list)
    
    # 风格配置快照
    style_profile_snapshot: Optional[Dict[str, Any]] = None
    
    # 统计
    @property
    def panel_count(self) -> int:
        return len(self.panels)
    
    @property
    def total_duration_sec(self) -> Optional[float]:
        durations = [p.duration_sec for p in self.panels if p.duration_sec]
        return sum(durations) if durations else None


@dataclass
class ArtifactFileRef:
    """产物文件引用"""
    storage_key: str  # MinIO 存储 key 或完整 URL
    dest_relpath: str  # 目标相对路径（在 bundle 内）
    required: bool = True  # 是否必须存在
    
    # 元数据
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None


@dataclass
class PanelArtifactPlan:
    """面板产物计划 - 这一格需要拉哪些文件"""
    panel_id: str
    panel_index_str: str  # "0001"
    
    # LayerPack 相关
    layerpack_id: Optional[str] = None
    layerpack_manifest_url: Optional[str] = None
    layerpack_files: List[ArtifactFileRef] = field(default_factory=list)
    
    # Typeset 相关
    typeset_id: Optional[str] = None
    typeset_png_url: Optional[str] = None
    bubbles_json: Optional[Dict] = None
    
    # QA 相关
    qa_json_url: Optional[str] = None
    qa_data: Optional[Dict] = None
    
    # 预览图（typeset 优先，fallback full）
    preview_image_url: Optional[str] = None
    uploaded_preview_url: Optional[str] = None  # 上传后的在线预览 URL
    
    # 是否有效
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def add_layerpack_file(self, storage_key: str, dest_relpath: str, required: bool = True):
        """添加 LayerPack 文件到计划"""
        self.layerpack_files.append(ArtifactFileRef(
            storage_key=storage_key,
            dest_relpath=dest_relpath,
            required=required
        ))


@dataclass
class BundleBuildContext:
    """Bundle 构建上下文"""
    export_id: str
    job_id: str
    chapter_id: str
    
    # 时间戳
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    # 临时目录
    staging_dir: Optional[str] = None
    
    # 进度回调
    progress_callback: Optional[callable] = None
    
    def report_progress(self, stage: str, progress: float, message: str = None, panel_index: str = None):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(
                job_id=self.job_id,
                stage=stage,
                progress=progress,
                message=message,
                panel_index=panel_index
            )


@dataclass
class BundleBuildResult:
    """Bundle 构建结果"""
    success: bool
    
    # 文件路径
    staging_dir: Optional[str] = None
    bundle_local_path: Optional[str] = None
    
    # 上传后的 URL
    bundle_url: Optional[str] = None
    manifest_url: Optional[str] = None
    
    # 统计
    panel_count: int = 0
    total_bytes: int = 0
    duration_ms: int = 0
    
    # 错误信息
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_panel_index: Optional[str] = None
    
    # QA 汇总
    qa_summary: Optional[Dict[str, Any]] = None
    needs_fix_panels: List[str] = field(default_factory=list)


@dataclass
class GateCheckResult:
    """导出门禁检查结果"""
    passed: bool
    
    # 必须项检查
    missing_required: List[str] = field(default_factory=list)  # 缺少必须文件的面板
    corrupt_manifests: List[str] = field(default_factory=list)  # 清单损坏的面板
    resolution_mismatch: List[str] = field(default_factory=list)  # 分辨率不匹配的面板
    
    # 警告项（不阻止导出）
    low_qa_panels: List[str] = field(default_factory=list)  # QA 低分面板
    missing_typeset: List[str] = field(default_factory=list)  # 缺少排版的面板
    
    # 汇总
    @property
    def error_count(self) -> int:
        return len(self.missing_required) + len(self.corrupt_manifests) + len(self.resolution_mismatch)
    
    @property
    def warning_count(self) -> int:
        return len(self.low_qa_panels) + len(self.missing_typeset)
    
    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "missing_required": self.missing_required,
            "corrupt_manifests": self.corrupt_manifests,
            "resolution_mismatch": self.resolution_mismatch,
            "low_qa_panels": self.low_qa_panels,
            "missing_typeset": self.missing_typeset
        }
