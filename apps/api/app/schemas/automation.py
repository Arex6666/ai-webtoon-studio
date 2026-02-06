"""
Automation Schemas - 自动化流程数据模型
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class AutomationStage(str, Enum):
    """自动化阶段"""
    PENDING = "pending"
    PARSING = "parsing"
    CHARACTER_CHAIN = "character_chain"
    SCENE_CHAIN = "scene_chain"
    BINDING = "binding"
    PLANNING = "planning"
    COMPLETED = "completed"
    FAILED = "failed"


class AutomationConfig(BaseModel):
    """自动化配置"""
    auto_create_assets: bool = Field(
        default=True,
        description="自动创建缺失的资产"
    )
    auto_generate_portraits: bool = Field(
        default=False,
        description="自动生成角色定妆照（需要 ComfyUI）"
    )
    auto_generate_backgrounds: bool = Field(
        default=False,
        description="自动生成场景背景图（需要 ComfyUI）"
    )
    auto_extract_embeddings: bool = Field(
        default=True,
        description="自动提取 FaceID Embedding"
    )
    auto_generate_control_maps: bool = Field(
        default=True,
        description="自动生成场景控制图（Depth/Canny/Lineart）"
    )
    director_preset: str = Field(
        default="default",
        description="导演预设: default/romance/thriller/contemplative"
    )


class CharacterChainResult(BaseModel):
    """角色处理链结果"""
    character_id: str
    ref_id: str  # ScriptIR 中的引用 ID
    name: str
    aliases: List[str] = Field(default_factory=list)
    
    # 状态
    asset_created: bool = False
    asset_existed: bool = False
    asset_id: Optional[str] = None
    
    # Embedding
    embedding_extracted: bool = False
    embedding_path: Optional[str] = None
    embedding_source_count: int = 0
    
    # 错误
    errors: List[str] = Field(default_factory=list)


class SceneChainResult(BaseModel):
    """场景处理链结果"""
    scene_id: str
    ref_id: str  # ScriptIR 中的引用 ID
    name: str
    location_type: str = "indoor"
    
    # 状态
    asset_created: bool = False
    asset_existed: bool = False
    asset_id: Optional[str] = None
    
    # 锚点和控制图
    anchor_generated: bool = False
    anchor_path: Optional[str] = None
    control_maps: Dict[str, str] = Field(default_factory=dict)
    
    # 错误
    errors: List[str] = Field(default_factory=list)


class AutomationProgress(BaseModel):
    """自动化进度"""
    stage: AutomationStage = AutomationStage.PENDING
    progress: float = Field(ge=0.0, le=100.0, default=0.0)
    current_task: str = ""
    
    # 统计
    total_characters: int = 0
    processed_characters: int = 0
    total_scenes: int = 0
    processed_scenes: int = 0


class AutomationResult(BaseModel):
    """自动化结果"""
    success: bool
    chapter_id: str
    
    # 进度
    progress: AutomationProgress = Field(default_factory=AutomationProgress)
    
    # 结果
    characters: List[CharacterChainResult] = Field(default_factory=list)
    scenes: List[SceneChainResult] = Field(default_factory=list)
    
    # 生成的资源
    storyboard_plan_id: Optional[str] = None
    draft_id: Optional[str] = None
    
    # 统计
    assets_created: int = 0
    embeddings_extracted: int = 0
    control_maps_generated: int = 0
    
    # 错误和警告
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ============ API Request/Response Models ============

class RunAutomationRequest(BaseModel):
    """运行自动化请求"""
    script_text: str = Field(..., min_length=10, description="剧本文本")
    config: AutomationConfig = Field(default_factory=AutomationConfig)


class AutomationStatusResponse(BaseModel):
    """自动化状态响应"""
    job_id: str
    chapter_id: str
    status: AutomationStage
    progress: float
    result: Optional[AutomationResult] = None
    error: Optional[str] = None
