"""
Tier Configuration - 渲染质量层级预设
Preview/Production/Hero 三级渲染质量控制

E1: Preview/Final Two-Stage Rendering
"""
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class TierPreset:
    """渲染层级预设"""
    name: str
    steps: int
    width: int
    height: int
    cfg_scale: float
    cost_multiplier: float
    description: str


# Tier presets: fast preview, normal production, hero quality
TIER_PRESETS: Dict[str, TierPreset] = {
    "fast": TierPreset(
        name="fast",
        steps=8,
        width=540,
        height=960,
        cfg_scale=5.0,
        cost_multiplier=0.2,
        description="Fast preview - low resolution, fewer steps",
    ),
    "normal": TierPreset(
        name="normal",
        steps=20,
        width=1080,
        height=1920,
        cfg_scale=7.0,
        cost_multiplier=1.0,
        description="Production quality - standard resolution",
    ),
    "hero": TierPreset(
        name="hero",
        steps=40,
        width=1440,
        height=2560,
        cfg_scale=8.0,
        cost_multiplier=2.5,
        description="Hero quality - high resolution, more steps",
    ),
}

DEFAULT_TIER = "normal"


def get_tier_preset(tier: str) -> TierPreset:
    """Get tier preset by name, fallback to normal."""
    return TIER_PRESETS.get(tier, TIER_PRESETS[DEFAULT_TIER])


def get_tier_cost_multiplier(tier: str) -> float:
    """Get the cost multiplier for a tier."""
    preset = get_tier_preset(tier)
    return preset.cost_multiplier


def apply_tier_to_context(context_dict: Dict[str, Any], tier: str) -> Dict[str, Any]:
    """
    Apply tier preset values onto a render context dict.
    Only overrides steps, width, height, cfg_scale.
    """
    preset = get_tier_preset(tier)
    context_dict["steps"] = preset.steps
    context_dict["width"] = preset.width
    context_dict["height"] = preset.height
    context_dict["cfg_scale"] = preset.cfg_scale
    return context_dict


def list_tiers() -> list:
    """List all available tiers with info."""
    return [
        {
            "name": preset.name,
            "steps": preset.steps,
            "width": preset.width,
            "height": preset.height,
            "cost_multiplier": preset.cost_multiplier,
            "description": preset.description,
        }
        for preset in TIER_PRESETS.values()
    ]
