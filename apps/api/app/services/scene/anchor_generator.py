"""
S5-SC: Scene Anchor Generator

从场景描述生成空镜锚点图。
"""
import logging
import random
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SceneAnchorSpec(BaseModel):
    """场景锚点规格"""
    scene_id: str
    name: str
    location: str = "generic indoor"
    time_of_day: str = "day"
    mood: str = "neutral"
    style_profile: str = "A"


class AnchorResult(BaseModel):
    """锚点生成结果"""
    success: bool
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    meta: dict = {}
    error: Optional[str] = None


# Style profiles for scene generation
STYLE_PROFILES = {
    "A": {
        "positive": "empty scene, no people, clean composition, cinematic lighting, high quality background art, detailed environment",
        "negative": "people, characters, faces, text, watermark, low quality, blurry"
    },
    "B": {
        "positive": "anime background, empty room, detailed scenery, professional illustration, vibrant colors",
        "negative": "people, characters, text, watermark, poorly drawn"
    }
}


def _enforce_seedream_min_pixels(size: tuple[int, int]) -> tuple[int, int]:
    """Seedream 4.5 requires ≥3,686,400 pixels (e.g. 1920×1920). Small callers
    (e.g. legacy default 768×512) are bumped up to a 16:9-ish landscape default.

    Callers needing a specific aspect ratio should pass an already-large size.
    """
    width, height = size
    if width * height >= 3_686_400:
        return width, height
    # Default scene anchor: 2304×1632 = 3,760,128 pixels (~16:9, slight pad)
    return 2304, 1632


def compose_anchor_prompt(spec: SceneAnchorSpec) -> tuple[str, str]:
    """
    组装场景锚点生成 Prompt
    
    Returns:
        (positive_prompt, negative_prompt)
    """
    style = STYLE_PROFILES.get(spec.style_profile, STYLE_PROFILES["A"])
    
    # Time of day mapping
    time_lighting = {
        "dawn": "soft warm morning light, golden hour",
        "day": "bright natural lighting, clear daylight",
        "dusk": "warm sunset colors, orange and purple sky",
        "night": "dark atmosphere, moonlight, artificial lights"
    }.get(spec.time_of_day, "natural lighting")
    
    # Mood mapping
    mood_atmosphere = {
        "romantic": "warm colors, soft focus, dreamy atmosphere",
        "tense": "dramatic shadows, high contrast, moody",
        "calm": "peaceful, serene, gentle colors",
        "exciting": "dynamic composition, vibrant energy"
    }.get(spec.mood, "balanced atmosphere")
    
    positive = f"{spec.location}, {time_lighting}, {mood_atmosphere}, {style['positive']}"
    negative = style["negative"]
    
    return positive.strip(), negative.strip()


async def generate_scene_anchor(
    spec: SceneAnchorSpec,
    provider: str = "mock",
    size: tuple[int, int] = (768, 512),
    seed: Optional[int] = None,
    output_dir: Optional[str] = None
) -> AnchorResult:
    """
    生成场景锚点图
    
    Args:
        spec: 场景规格
        provider: 生成服务 (mock/comfyui)
        size: 图像尺寸 (宽, 高)
        seed: 随机种子
        output_dir: 输出目录
        
    Returns:
        AnchorResult
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    
    positive, negative = compose_anchor_prompt(spec)
    
    logger.info(f"[SceneAnchor] Generating for {spec.name} ({spec.scene_id})")
    logger.debug(f"[SceneAnchor] Prompt: {positive[:100]}...")
    
    if provider == "mock":
        return await _generate_mock(spec, seed)
    elif provider == "comfyui":
        return await _generate_comfyui(spec, positive, negative, size, seed, output_dir)
    else:
        return AnchorResult(success=False, error=f"Unknown provider: {provider}")


async def _generate_mock(spec: SceneAnchorSpec, seed: int) -> AnchorResult:
    """Mock 生成器"""
    # 模拟生成延迟
    import asyncio
    await asyncio.sleep(0.5)
    
    mock_path = f"/storage/anchors/{spec.scene_id}/anchor_{seed}.png"
    
    return AnchorResult(
        success=True,
        image_path=mock_path,
        meta={
            "seed": seed,
            "provider": "mock",
            "prompt_hash": hash(spec.location)
        }
    )


async def _generate_comfyui(
    spec: SceneAnchorSpec,
    positive: str,
    negative: str,
    size: tuple[int, int],
    seed: int,
    output_dir: Optional[str]
) -> AnchorResult:
    """ComfyUI 生成器"""
    # TODO: 实现真实的 ComfyUI 调用
    # 目前先使用 Mock
    logger.warning("[SceneAnchor] ComfyUI not implemented, falling back to mock")
    return await _generate_mock(spec, seed)
