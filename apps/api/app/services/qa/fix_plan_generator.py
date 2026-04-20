"""
Fix Plan Generator - 修复方案生成器 (E5: NeedsFix Workflow)
Maps QA issue codes to ranked fix strategies with cost + probability.
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FixOption(BaseModel):
    """A single fix option with cost and success probability."""
    fix_type: str  # change_seed, boost_faceid, increase_steps, inpaint, upscale, manual
    description: str
    parameter_changes: Dict[str, Any] = {}
    estimated_cost: float = 0.0
    success_probability: float = 0.5
    priority: int = 0  # lower = higher priority


# Issue code → ranked fix strategies
FIX_STRATEGIES: Dict[str, List[Dict[str, Any]]] = {
    "BLACK_IMAGE": [
        {"fix_type": "change_seed", "description": "Change seed and re-render",
         "parameter_changes": {"seed": -1}, "success_probability": 0.8, "priority": 0},
        {"fix_type": "increase_steps", "description": "Increase sampling steps",
         "parameter_changes": {"steps_delta": 10}, "success_probability": 0.6, "priority": 1},
    ],
    "OVEREXPOSED": [
        {"fix_type": "change_seed", "description": "Change seed to reduce overexposure",
         "parameter_changes": {"seed": -1}, "success_probability": 0.7, "priority": 0},
        {"fix_type": "adjust_cfg", "description": "Lower CFG scale",
         "parameter_changes": {"cfg_delta": -1.5}, "success_probability": 0.6, "priority": 1},
    ],
    "BLURRY": [
        {"fix_type": "increase_steps", "description": "Increase sampling steps for sharpness",
         "parameter_changes": {"steps_delta": 10}, "success_probability": 0.7, "priority": 0},
        {"fix_type": "upscale", "description": "Upscale with sharpening",
         "parameter_changes": {"upscale": True}, "success_probability": 0.8, "priority": 1},
    ],
    "LOW_ENTROPY": [
        {"fix_type": "change_seed", "description": "Change seed for more variety",
         "parameter_changes": {"seed": -1}, "success_probability": 0.75, "priority": 0},
        {"fix_type": "adjust_cfg", "description": "Increase CFG for more detail",
         "parameter_changes": {"cfg_delta": 1.0}, "success_probability": 0.5, "priority": 1},
    ],
    "LOW_RESOLUTION": [
        {"fix_type": "upscale", "description": "Render at higher resolution",
         "parameter_changes": {"tier": "normal"}, "success_probability": 0.95, "priority": 0},
    ],
    "FACE_DRIFT": [
        {"fix_type": "boost_faceid", "description": "Boost FaceID weight",
         "parameter_changes": {"faceid_weight_delta": 0.15}, "success_probability": 0.7, "priority": 0},
        {"fix_type": "change_seed", "description": "Change seed with current FaceID",
         "parameter_changes": {"seed": -1}, "success_probability": 0.5, "priority": 1},
    ],
    "NO_FACE": [
        {"fix_type": "adjust_composition", "description": "Use closer shot type",
         "parameter_changes": {"shot_type": "close"}, "success_probability": 0.6, "priority": 0},
        {"fix_type": "change_seed", "description": "Retry with new seed",
         "parameter_changes": {"seed": -1}, "success_probability": 0.4, "priority": 1},
    ],
    "SEGMENTATION_FAIL": [
        {"fix_type": "change_model", "description": "Switch segmentation model",
         "parameter_changes": {"segmentation_model": "isnet-anime"}, "success_probability": 0.6, "priority": 0},
        {"fix_type": "change_seed", "description": "Retry with new seed",
         "parameter_changes": {"seed": -1}, "success_probability": 0.4, "priority": 1},
    ],
}


def generate_fix_options(
    issues: List[Dict[str, Any]],
    panel_id: str,
    provider: str = "doubao",
    tier: str = "normal",
    cost_per_render: float = 0.04,
) -> List[FixOption]:
    """
    Generate ranked fix options for a list of QA issues.

    Args:
        issues: List of issue dicts with 'code', 'level', 'message'
        panel_id: The panel that needs fixing
        provider: Current render provider
        tier: Current render tier
        cost_per_render: Base cost per render for estimation

    Returns:
        List of FixOption sorted by priority
    """
    options: List[FixOption] = []
    seen_types = set()

    for issue in issues:
        code = issue.get("code", "")
        strategies = FIX_STRATEGIES.get(code, [])

        for strat in strategies:
            fix_type = strat["fix_type"]
            if fix_type in seen_types:
                continue
            seen_types.add(fix_type)

            # Estimate cost based on fix type
            estimated_cost = cost_per_render
            if fix_type == "upscale":
                estimated_cost = cost_per_render * 2.0
            elif fix_type == "increase_steps":
                estimated_cost = cost_per_render * 1.5

            options.append(FixOption(
                fix_type=strat["fix_type"],
                description=strat["description"],
                parameter_changes=strat.get("parameter_changes", {}),
                estimated_cost=round(estimated_cost, 4),
                success_probability=strat.get("success_probability", 0.5),
                priority=strat.get("priority", 99),
            ))

    # Sort by priority (lower = better)
    options.sort(key=lambda o: o.priority)
    return options


def get_best_fix(issues: List[Dict[str, Any]], **kwargs) -> Optional[FixOption]:
    """Get the single best fix option for the issues."""
    options = generate_fix_options(issues, **kwargs)
    return options[0] if options else None
