# Pydantic Schemas - JSON Schema Definitions
from .chapter_layout import ChapterLayout, PanelSlot, PanelWeight, ReadingFlow
from .panel_spec import (
    PanelSpec,
    CharacterRef,
    SceneRef,
    CompositionSettings,
    DialogueLine,
    BubblePlan,
    BubbleDraft,
    BubbleFinal,
    BubbleCandidate,
    PromptSettings,
    LookSettings,
    ActSettings,
    CameraMotion,
    Warning,
    RenderInfo,
    PanelSpecCreate,
    PanelSpecUpdate as PanelSpecUpdateSchema,
    ShotType,
    CameraAngle,
    DialogueType,
    BubbleStyle,
    NineGrid,
    RenderTier,
    WarningSeverity,
    PanelStatus,
)
from .shot_spec import (
    ShotSpec,
    NarrativeSpec,
    CameraSpec,
    TimingSpec,
    StyleSpec,
    EnvironmentSpec,
    CastSpec,
    SceneSpec,
    DialogueSpec,
    DialogueItem,
    ControlSpec,
    EnginePlan,
    CharacterPlacement,
    ShotScale,
    CameraMovement,
    LensType,
    WeatherType,
    TimeOfDay,
    ConsistencyLevel,
    ControlStrength,
    SeedPolicy,
)
from .layer_pack_meta import (
    LayerPackMeta, 
    LayerFiles,             # 图层文件路径
    BoundingBox,            # 边界框
    BBoxInfo,               # 边界框信息
    GenerationParams,       # 生成参数
    QAResult,               # QA 结果
    QAIssue,                # QA 问题
    LayerPackCreate,        # 创建图层包请求
    LayerPackUpdate,        # 更新图层包
)
from .common import (
    # 通用响应
    StatusResponse,
    HealthResponse,
    PaginatedResponse,
    ErrorResponse,
    # Project
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    # Chapter
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    # Panel
    PanelCreate,
    PanelUpdate,
    PanelSpecUpdate,
    PanelResponse,
    # Asset
    AssetCreate,
    AssetUpdate,
    AssetResponse,
    # RenderJob
    RenderJobCreate,
    RenderJobResponse,
    # Studio
    ChapterStudioResponse,
    StudioCharacterSummary,
    StudioSceneSummary,
    StudioPanelSummary,
    StudioJobSummary,
    StudioWarning,
    # Script
    ScriptSubmitRequest,
    ScriptSubmitResponse,
    # Render
    RenderRequest,
    RenderResponse,
    # Export
    ExportStripRequest,
    ExportResponse,
    # WebSocket
    WSJobUpdate,
    WSPanelUpdate,
)

# 向后兼容的别名
CharacterPlacement = CharacterRef
CameraSettings = CompositionSettings
LayerFile = LayerFiles
QAScore = QAResult
