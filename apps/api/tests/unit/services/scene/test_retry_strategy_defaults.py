"""Verify retry_strategy defaults route to real implementations (Phase C)."""
import inspect

from app.services.scene import retry_strategy


def test_enqueue_default_anchor_provider_is_doubao():
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert sig.parameters["anchor_provider"].default == "doubao"


def test_enqueue_default_control_map_provider_is_cv2():
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert sig.parameters["control_map_provider"].default == "cv2"


def test_enqueue_no_longer_has_legacy_provider_param():
    """Old single 'provider' kwarg should be gone — split into two."""
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert "provider" not in sig.parameters
