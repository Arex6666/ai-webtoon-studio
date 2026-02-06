"""
生产规格常量定义
LayerPack Manifest v1 规范的代码实现
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime


# ============ 画幅规格 ============

class AspectPreset(str, Enum):
    """画幅预设"""
    WEBTOON_STANDARD = "webtoon_standard"  # 1080x1920 9:16
    WEBTOON_HD = "webtoon_hd"              # 1440x2560 9:16
    SQUARE = "square"                       # 1024x1024 1:1
    LANDSCAPE = "landscape"                 # 1920x1080 16:9


ASPECT_DIMENSIONS = {
    AspectPreset.WEBTOON_STANDARD: {"width": 1080, "height": 1920, "aspect": "9:16"},
    AspectPreset.WEBTOON_HD: {"width": 1440, "height": 2560, "aspect": "9:16"},
    AspectPreset.SQUARE: {"width": 1024, "height": 1024, "aspect": "1:1"},
    AspectPreset.LANDSCAPE: {"width": 1920, "height": 1080, "aspect": "16:9"},
}

DEFAULT_ASPECT = AspectPreset.WEBTOON_STANDARD
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920


# ============ MinIO 配置 ============

MINIO_BUCKET = "webtoon-studio"

def build_minio_key(
    project_id: str,
    chapter_id: str,
    panel_id: str,
    attempt_id: str,
    filename: str
) -> str:
    """构建 MinIO 对象键"""
    return f"{project_id}/{chapter_id}/{panel_id}/{attempt_id}/{filename}"


def build_minio_prefix(
    project_id: str,
    chapter_id: Optional[str] = None,
    panel_id: Optional[str] = None,
    attempt_id: Optional[str] = None
) -> str:
    """构建 MinIO 前缀（用于列举）"""
    parts = [project_id]
    if chapter_id:
        parts.append(chapter_id)
    if panel_id:
        parts.append(panel_id)
    if attempt_id:
        parts.append(attempt_id)
    return "/".join(parts) + "/"


# ============ ID 生成 ============

import uuid
import time

def generate_project_id() -> str:
    return f"proj-{uuid.uuid4().hex[:8]}"

def generate_chapter_id(order: int) -> str:
    return f"ch-{order:03d}"

def generate_panel_id(order: int) -> str:
    return f"panel-{order:03d}"

def generate_attempt_id(attempt: int) -> str:
    return f"attempt-{attempt:03d}"

def generate_layerpack_id() -> str:
    timestamp = int(time.time())
    unique = uuid.uuid4().hex[:6]
    return f"lp-{timestamp}-{unique}"


# ============ Manifest Schema ============

class Dimensions(BaseModel):
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    aspect: str = "9:16"


class GenerationParams(BaseModel):
    seed: int
    model: str
    model_version: Optional[str] = None
    provider: str = "comfyui"
    steps: Optional[int] = 20
    cfg: Optional[float] = 7.5
    sampler: Optional[str] = "euler_a"
    scheduler: Optional[str] = "normal"


class Prompts(BaseModel):
    positive: str
    negative: Optional[str] = ""


class Outputs(BaseModel):
    full: str  # 必需
    background: Optional[str] = None
    character: Optional[str] = None
    lineart: Optional[str] = None
    alpha: Optional[str] = None


class Metadata(BaseModel):
    created_at: str
    duration_ms: Optional[int] = None
    cost: Optional[float] = None


class QAResult(BaseModel):
    score: float
    issues: List[str] = []


class AnchorRef(BaseModel):
    kind: str
    weight: float = 1.0


class LayerPackManifest(BaseModel):
    """LayerPack Manifest v1 完整结构"""
    version: str = "1.0.0"
    id: str
    panel_id: str
    project_id: str
    chapter_id: str
    attempt: int = 1
    
    dimensions: Dimensions
    generation: GenerationParams
    prompts: Prompts
    outputs: Outputs
    metadata: Metadata
    
    # 可选扩展
    identity_assets: Optional[List[str]] = None
    scene_assets: Optional[List[str]] = None
    style_profile_id: Optional[str] = None
    anchors: Optional[List[AnchorRef]] = None
    qa: Optional[QAResult] = None
    parent_layerpack_id: Optional[str] = None


def create_manifest(
    panel_id: str,
    project_id: str,
    chapter_id: str,
    seed: int,
    model: str,
    positive_prompt: str,
    negative_prompt: str = "",
    provider: str = "comfyui",
    attempt: int = 1,
    dimensions: Optional[Dict] = None,
) -> LayerPackManifest:
    """创建新的 LayerPack Manifest"""
    now = datetime.utcnow().isoformat() + "Z"
    lp_id = generate_layerpack_id()
    attempt_id = generate_attempt_id(attempt)
    
    dims = dimensions or ASPECT_DIMENSIONS[DEFAULT_ASPECT]
    
    return LayerPackManifest(
        id=lp_id,
        panel_id=panel_id,
        project_id=project_id,
        chapter_id=chapter_id,
        attempt=attempt,
        dimensions=Dimensions(**dims),
        generation=GenerationParams(
            seed=seed,
            model=model,
            provider=provider,
        ),
        prompts=Prompts(
            positive=positive_prompt,
            negative=negative_prompt,
        ),
        outputs=Outputs(
            full=f"{attempt_id}/full.png",
        ),
        metadata=Metadata(
            created_at=now,
        ),
    )


# ============ 文件名常量 ============

MANIFEST_FILENAME = "manifest.json"
FULL_LAYER_FILENAME = "full.png"
BACKGROUND_LAYER_FILENAME = "background.png"
CHARACTER_LAYER_FILENAME = "character.png"
LINEART_LAYER_FILENAME = "lineart.png"
ALPHA_LAYER_FILENAME = "alpha.png"

LAYER_FILENAMES = {
    "full": FULL_LAYER_FILENAME,
    "background": BACKGROUND_LAYER_FILENAME,
    "character": CHARACTER_LAYER_FILENAME,
    "lineart": LINEART_LAYER_FILENAME,
    "alpha": ALPHA_LAYER_FILENAME,
}
