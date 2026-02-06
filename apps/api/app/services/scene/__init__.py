"""
S5-SC: Scene Services

场景一致性自动化服务模块。
"""
from .anchor_generator import SceneAnchorSpec, generate_scene_anchor, AnchorResult
from .control_map_extractor import extract_control_maps, ControlMapResult
from .retry_strategy import enqueue_scene_anchor_generation

__all__ = [
    "SceneAnchorSpec",
    "generate_scene_anchor",
    "AnchorResult",
    "extract_control_maps",
    "ControlMapResult",
    "enqueue_scene_anchor_generation"
]
