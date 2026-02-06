"""
LayerPackMeta JSON Schema - 图层包元数据定义
渲染输出的结构化描述

遵循规范：
- files: {full, char, bg, fg, mask}
- bbox: {char_bbox, face_bbox?}
- params: {seed, template_id, style_profile_id}
- qa: {score, reasons:[]}
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class BoundingBox(BaseModel):
    """边界框"""
    x: float = Field(..., ge=0, le=1, description="左上角 X 坐标（百分比）")
    y: float = Field(..., ge=0, le=1, description="左上角 Y 坐标（百分比）")
    width: float = Field(..., ge=0, le=1, description="宽度（百分比）")
    height: float = Field(..., ge=0, le=1, description="高度（百分比）")
    confidence: float = Field(default=1.0, ge=0, le=1, description="检测置信度")
    label: Optional[str] = Field(default=None, description="标签（如角色名）")


class LayerFiles(BaseModel):
    """图层文件路径"""
    full: str = Field(..., description="完整合成图")
    char: Optional[str] = Field(default=None, description="角色层（已抠图）")
    bg: Optional[str] = Field(default=None, description="背景层")
    fg: Optional[str] = Field(default=None, description="前景层")
    mask: Optional[str] = Field(default=None, description="遮罩层")
    depth: Optional[str] = Field(default=None, description="深度图")
    lineart: Optional[str] = Field(default=None, description="线稿图")
    # 额外图层
    extras: Dict[str, str] = Field(default_factory=dict, description="额外图层")


class BBoxInfo(BaseModel):
    """边界框信息"""
    char_bbox: Optional[BoundingBox] = Field(default=None, description="角色整体边界框")
    face_bbox: Optional[BoundingBox] = Field(default=None, description="人脸边界框")
    body_bbox: Optional[BoundingBox] = Field(default=None, description="身体边界框")
    # 多角色支持
    all_characters: List[BoundingBox] = Field(default_factory=list, description="所有角色边界框")
    all_faces: List[BoundingBox] = Field(default_factory=list, description="所有人脸边界框")


class GenerationParams(BaseModel):
    """生成参数"""
    seed: int = Field(..., description="随机种子")
    template_id: str = Field(default="default", description="工作流模板 ID")
    style_profile_id: Optional[str] = Field(default=None, description="风格配置 ID")
    # ComfyUI 参数
    steps: int = Field(default=30, description="采样步数")
    cfg_scale: float = Field(default=7.0, description="CFG 强度")
    sampler: str = Field(default="euler", description="采样器")
    scheduler: str = Field(default="normal", description="调度器")
    denoise: float = Field(default=1.0, description="降噪强度")
    # ControlNet 参数
    controlnet_weights: Dict[str, float] = Field(
        default_factory=dict, 
        description="ControlNet 权重 {type: weight}"
    )
    # FaceID 参数
    faceid_strength: float = Field(default=0.8, description="FaceID 强度")
    # 实际使用的提示词
    actual_positive: str = Field(default="", description="实际使用的正向提示词")
    actual_negative: str = Field(default="", description="实际使用的负向提示词")


class QAIssue(BaseModel):
    """QA 问题"""
    type: str = Field(..., description="问题类型")
    severity: str = Field(default="warning", description="严重程度: info/warning/error")
    description: str = Field(..., description="问题描述")
    location: Optional[str] = Field(default=None, description="问题位置")
    auto_fixable: bool = Field(default=False, description="是否可自动修复")
    suggested_action: Optional[str] = Field(default=None, description="建议操作")


class QAResult(BaseModel):
    """QA 结果"""
    score: float = Field(default=0.0, ge=0, le=1, description="总体评分")
    passed: bool = Field(default=False, description="是否通过")
    
    # 分项评分
    consistency_score: float = Field(default=0.0, ge=0, le=1, description="角色一致性评分")
    segmentation_score: float = Field(default=0.0, ge=0, le=1, description="抠图质量评分")
    composition_score: float = Field(default=0.0, ge=0, le=1, description="构图评分")
    style_score: float = Field(default=0.0, ge=0, le=1, description="风格一致性评分")
    
    # 问题列表
    issues: List[QAIssue] = Field(default_factory=list, description="问题列表")
    
    # 推荐操作
    needs_manual_fix: bool = Field(default=False, description="是否需要手动修复")
    recommended_action: Optional[str] = Field(default=None, description="推荐操作")


class LayerPackMeta(BaseModel):
    """
    图层包元数据 - 渲染输出的完整描述
    """
    # 基本信息
    layerpack_id: str = Field(..., description="图层包 ID")
    panel_id: str = Field(..., description="关联的分镜 ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    # 图层文件
    files: LayerFiles = Field(..., description="图层文件路径")
    
    # 边界框信息
    bbox: BBoxInfo = Field(default_factory=BBoxInfo, description="边界框信息")
    
    # 生成参数
    params: GenerationParams = Field(..., description="生成参数")
    
    # QA 结果
    qa: QAResult = Field(default_factory=QAResult, description="QA 结果")
    
    # 尺寸信息
    width: int = Field(..., description="图片宽度")
    height: int = Field(..., description="图片高度")
    
    # 状态
    status: str = Field(default="completed", description="状态: generating/completed/failed")
    
    # 版本与历史
    version: int = Field(default=1, description="版本号")
    parent_id: Optional[str] = Field(default=None, description="父版本 ID（用于重试）")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "layerpack_id": "lp_001",
                "panel_id": "panel_001",
                "created_at": "2024-01-15T10:30:00Z",
                "files": {
                    "full": "layerpacks/lp_001/full.png",
                    "char": "layerpacks/lp_001/char.png",
                    "bg": "layerpacks/lp_001/bg.png",
                    "mask": "layerpacks/lp_001/mask.png"
                },
                "bbox": {
                    "char_bbox": {"x": 0.2, "y": 0.1, "width": 0.6, "height": 0.8, "confidence": 0.95},
                    "face_bbox": {"x": 0.35, "y": 0.15, "width": 0.2, "height": 0.15, "confidence": 0.98}
                },
                "params": {
                    "seed": 12345,
                    "template_id": "webtoon_v1",
                    "style_profile_id": "korean_romantic",
                    "steps": 30,
                    "cfg_scale": 7.0,
                    "faceid_strength": 0.8
                },
                "qa": {
                    "score": 0.85,
                    "passed": True,
                    "consistency_score": 0.9,
                    "segmentation_score": 0.8,
                    "composition_score": 0.85,
                    "style_score": 0.85,
                    "issues": [],
                    "needs_manual_fix": False
                },
                "width": 800,
                "height": 1200,
                "status": "completed",
                "version": 1
            }
        }


# ===== 辅助模型 =====

class LayerPackCreate(BaseModel):
    """创建图层包请求"""
    panel_id: str = Field(..., description="分镜 ID")
    template_id: str = Field(default="default", description="工作流模板 ID")
    seed: Optional[int] = Field(default=None, description="随机种子（为空则随机）")
    style_profile_id: Optional[str] = Field(default=None, description="风格配置 ID")


class LayerPackUpdate(BaseModel):
    """更新图层包"""
    qa: Optional[QAResult] = None
    bbox: Optional[BBoxInfo] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
