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
    elif provider == "doubao":
        return await _generate_doubao_seedream(spec, positive, negative, size, seed)
    elif provider == "comfyui":
        # ComfyUI path is deferred until home-GPU deployment (B-1 Phase A territory).
        # Fall through to Doubao for safety.
        logger.warning("[SceneAnchor] ComfyUI not implemented, falling back to doubao")
        return await _generate_doubao_seedream(spec, positive, negative, size, seed)
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


async def _generate_doubao_seedream(
    spec: SceneAnchorSpec,
    positive: str,
    negative: str,
    size: tuple[int, int],
    seed: int,
) -> AnchorResult:
    """Generate scene anchor via Doubao Seedream 4.5 + re-store under the
    canonical AnchorStorage path.

    The provider already persists the image under the `images/` MinIO prefix.
    We re-save under `anchors/scenes/{scene_id}/anchor.png` to give the scene
    its canonical address.
    """
    from app.services.layer_factory.doubao_image_provider import (
        get_doubao_image_provider, DoubaoImageRequest, SEEDREAM_MODEL,
    )
    from app.services.scene_anchor.anchor_storage import get_anchor_storage
    from app.core.storage import get_storage_client

    provider = get_doubao_image_provider()
    if not provider.api_key:
        return AnchorResult(
            success=False,
            error="ARK_API_KEY / DOUBAO_API_KEY not configured",
        )

    width, height = _enforce_seedream_min_pixels(size)

    req = DoubaoImageRequest(
        prompt=positive,
        negative_prompt=negative,
        width=width,
        height=height,
        seed=seed,
    )

    try:
        resp = await provider.generate(req)
    except Exception as e:
        logger.exception("[SceneAnchor] Seedream call raised")
        return AnchorResult(success=False, error=f"Seedream call raised: {e!r}")

    if not resp.success:
        return AnchorResult(
            success=False,
            error=resp.error or "Seedream generation failed",
        )

    # Resolve image bytes — provider may have persisted bytes inline OR returned
    # a storage key OR returned an http(s) URL (fallback when persist failed).
    image_bytes = resp.image_data
    if image_bytes is None and resp.image_url:
        if resp.image_url.startswith(("http://", "https://")):
            import httpx
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.get(resp.image_url)
                    r.raise_for_status()
                    image_bytes = r.content
            except Exception as e:
                logger.exception("[SceneAnchor] Failed to download Seedream temp URL")
                return AnchorResult(success=False, error=f"download failed: {e!r}")
        else:
            try:
                sc = get_storage_client()
                image_bytes = await sc.download_bytes(resp.image_url)
            except Exception as e:
                logger.exception("[SceneAnchor] Failed to fetch persisted Seedream bytes")
                return AnchorResult(success=False, error=f"storage fetch failed: {e!r}")

    if not image_bytes:
        return AnchorResult(
            success=False,
            error="Seedream returned neither image_data nor a usable image_url",
        )

    storage = get_anchor_storage()
    paths = await storage.save_anchor(
        scene_id=spec.scene_id,
        anchor_image=image_bytes,
        control_maps={},
        metadata={
            "prompt": positive,
            "negative_prompt": negative,
            "seed": seed,
            "provider": "doubao-seedream",
            "model": SEEDREAM_MODEL,
            "size": [width, height],
        },
    )

    return AnchorResult(
        success=True,
        image_path=paths["anchor"],
        image_url=storage.get_anchor_url(spec.scene_id),
        meta={
            "seed": seed,
            "provider": "doubao-seedream",
            "model": SEEDREAM_MODEL,
            "prompt_hash": hash(positive),
        },
    )
