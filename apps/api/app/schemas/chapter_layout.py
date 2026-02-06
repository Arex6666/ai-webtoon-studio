"""
ChapterLayout JSON Schema - 章节布局定义
Single Source of Truth for chapter structure

遵循规范：
- mode: strip|page
- panels_order: [panel_id...]
- panel_weights: {panel_id: hero|normal|fast 或数值权重}
- export: {width, base_panel_height, spacing, background_color}
- default_style_profile_id
- default_camera_suggestions（可选）
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum


class LayoutMode(str, Enum):
    """布局模式"""
    STRIP = "strip"        # 竖向长条漫（Webtoon）
    PAGE = "page"          # 分页漫画
    BOARD = "board"        # 无限画布（编辑用）


class PanelWeight(str, Enum):
    """分镜权重 - 决定分镜在长条漫中的视觉重要性"""
    HERO = "hero"              # 重点格（大图，高潮场景）- 1.5x~2x 高度
    HIGHLIGHT = "highlight"    # 重点格（同 hero）
    NORMAL = "normal"          # 普通格 - 1x 高度
    TRANSITION = "transition"  # 过场格（小图）- 0.5x~0.7x 高度
    FAST = "fast"              # 快速格（同 transition）


class ReadingFlow(str, Enum):
    """阅读流向"""
    VERTICAL = "vertical"      # 竖读（Webtoon 标准）
    HORIZONTAL = "horizontal"  # 横读
    RTL = "rtl"               # 从右到左（日漫）
    ZIGZAG = "zigzag"         # 之字形（传统漫画）


class PanelSlot(BaseModel):
    """分镜槽位 - 定义分镜在章节中的位置和权重"""
    panel_id: str = Field(..., description="关联的 Panel ID")
    weight: PanelWeight = Field(default=PanelWeight.NORMAL, description="分镜权重")
    height_ratio: float = Field(default=1.0, ge=0.3, le=3.0, description="相对高度比例")
    order: int = Field(default=0, description="排序序号")
    # 扩展属性
    width_ratio: float = Field(default=1.0, ge=0.3, le=1.0, description="宽度比例（用于并排）")
    offset_x: float = Field(default=0, ge=-0.5, le=0.5, description="水平偏移")
    group_id: Optional[str] = Field(default=None, description="分组 ID（用于并排分镜）")
    
    class Config:
        use_enum_values = True


class ExportConfig(BaseModel):
    """导出配置"""
    # 尺寸
    width: int = Field(default=800, ge=400, le=4000, description="长条漫宽度")
    base_panel_height: int = Field(default=1200, ge=400, le=2000, description="基准分镜高度")
    max_height: Optional[int] = Field(default=None, description="最大导出高度（超出则分割）")
    
    # 间距与背景
    spacing: int = Field(default=20, ge=0, le=100, description="分镜间距")
    padding: int = Field(default=0, ge=0, le=100, description="页面边距")
    background_color: str = Field(default="#FFFFFF", description="背景颜色")
    
    # 格式
    format: Literal["png", "jpg", "webp"] = Field(default="png", description="导出格式")
    quality: int = Field(default=95, ge=1, le=100, description="图片质量")
    
    # 特效
    add_motion: bool = Field(default=False, description="是否添加微动画（导出视频）")
    motion_fps: int = Field(default=24, ge=12, le=60, description="动画帧率")
    motion_duration: float = Field(default=3.0, ge=1.0, le=30.0, description="每分镜动画时长")


class CameraSuggestion(BaseModel):
    """默认镜头建议"""
    default_shot_flow: List[str] = Field(
        default_factory=lambda: ["wide", "medium", "close", "medium"],
        description="默认景别流程"
    )
    auto_vary_angle: bool = Field(default=True, description="自动变化角度")
    avoid_jump_cut: bool = Field(default=True, description="避免跳跃剪辑")


class ScriptMetadata(BaseModel):
    """剧本元数据"""
    original_script: str = Field(default="", description="原始剧本文本")
    parsed_at: Optional[str] = Field(default=None, description="解析时间")
    llm_model: Optional[str] = Field(default=None, description="使用的 LLM 模型")
    word_count: int = Field(default=0, description="字数统计")


class ChapterLayout(BaseModel):
    """
    章节布局 - Single Source of Truth
    定义章节的结构、分镜顺序和导出配置
    """
    # 基本信息
    chapter_id: str = Field(..., description="章节 ID")
    title: str = Field(default="未命名章节", description="章节标题")
    description: Optional[str] = Field(default=None, description="章节描述/大纲")
    
    # 布局模式
    mode: LayoutMode = Field(default=LayoutMode.STRIP, description="布局模式")
    reading_flow: ReadingFlow = Field(default=ReadingFlow.VERTICAL, description="阅读流向")
    
    # 分镜顺序
    panels_order: List[str] = Field(default_factory=list, description="分镜 ID 顺序列表")
    panel_weights: Dict[str, PanelWeight] = Field(
        default_factory=dict, 
        description="分镜权重映射 {panel_id: weight}"
    )
    
    # 详细槽位配置（可选，用于更精细控制）
    panels: List[PanelSlot] = Field(default_factory=list, description="分镜槽位列表")
    
    # 导出配置
    export: ExportConfig = Field(default_factory=ExportConfig, description="导出配置")
    
    # 默认风格
    default_style_profile_id: Optional[str] = Field(default=None, description="默认风格配置 ID")
    
    # 默认镜头建议
    default_camera: CameraSuggestion = Field(
        default_factory=CameraSuggestion, 
        description="默认镜头建议"
    )
    
    # 剧本元数据
    script: ScriptMetadata = Field(default_factory=ScriptMetadata, description="剧本元数据")
    
    # 章节状态
    status: Literal["draft", "storyboarded", "rendering", "rendered", "approved", "exported"] = Field(
        default="draft", description="章节状态"
    )
    
    # 统计信息
    stats: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_panels": 0,
            "rendered_panels": 0,
            "failed_panels": 0,
            "avg_qa_score": 0.0
        },
        description="统计信息"
    )
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    version: int = Field(default=1, description="Schema 版本号")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "chapter_id": "chapter_001",
                "title": "第一章：相遇",
                "description": "男女主角在咖啡厅偶遇，命运的齿轮开始转动",
                "mode": "strip",
                "reading_flow": "vertical",
                "panels_order": ["panel_001", "panel_002", "panel_003", "panel_004"],
                "panel_weights": {
                    "panel_001": "hero",
                    "panel_002": "normal",
                    "panel_003": "normal",
                    "panel_004": "highlight"
                },
                "export": {
                    "width": 800,
                    "base_panel_height": 1200,
                    "spacing": 20,
                    "background_color": "#FFFFFF",
                    "format": "png"
                },
                "default_style_profile_id": "style_korean_webtoon",
                "script": {
                    "original_script": "在一个阳光明媚的午后，李明走进了街角的咖啡厅...",
                    "word_count": 500
                },
                "status": "storyboarded",
                "stats": {
                    "total_panels": 4,
                    "rendered_panels": 2,
                    "failed_panels": 0,
                    "avg_qa_score": 0.85
                },
                "version": 1
            }
        }


# ===== API 请求模型 =====

class ChapterLayoutCreate(BaseModel):
    """创建章节布局"""
    title: str = Field(..., description="章节标题")
    description: Optional[str] = Field(default=None, description="章节描述")
    mode: LayoutMode = Field(default=LayoutMode.STRIP, description="布局模式")
    default_style_profile_id: Optional[str] = Field(default=None, description="默认风格")


class ChapterLayoutUpdate(BaseModel):
    """更新章节布局"""
    title: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[LayoutMode] = None
    reading_flow: Optional[ReadingFlow] = None
    panels_order: Optional[List[str]] = None
    panel_weights: Optional[Dict[str, PanelWeight]] = None
    export: Optional[ExportConfig] = None
    default_style_profile_id: Optional[str] = None
    default_camera: Optional[CameraSuggestion] = None
    status: Optional[str] = None


class ScriptSubmission(BaseModel):
    """剧本提交"""
    script_text: str = Field(..., min_length=1, description="剧本文本")
    style_hint: Optional[str] = Field(default="korean_webtoon", description="风格提示")
    auto_storyboard: bool = Field(default=True, description="是否自动分镜")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息（角色、场景等）")


class PanelReorderRequest(BaseModel):
    """分镜重排序请求"""
    panels_order: List[str] = Field(..., description="新的分镜顺序")
    panel_weights: Optional[Dict[str, PanelWeight]] = Field(default=None, description="权重更新")
