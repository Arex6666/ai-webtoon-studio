"""Static-source regression: Phase C real implementations are live (not stubbed back to mock)."""
import inspect

from app.services.scene import anchor_generator, control_map_extractor, retry_strategy


def test_anchor_generator_imports_doubao_provider():
    """The doubao provider import must appear inside _generate_doubao_seedream."""
    src = inspect.getsource(anchor_generator)
    assert "from app.services.layer_factory.doubao_image_provider import" in src, \
        "anchor_generator no longer imports doubao_image_provider — Phase C regressed to mock"


def test_anchor_generator_has_doubao_function():
    assert hasattr(anchor_generator, "_generate_doubao_seedream"), \
        "anchor_generator missing _generate_doubao_seedream — Phase C regressed"


def test_anchor_generator_dispatches_doubao_provider():
    src = inspect.getsource(anchor_generator.generate_scene_anchor)
    assert 'provider == "doubao"' in src, \
        "generate_scene_anchor no longer routes 'doubao' provider — Phase C regressed"


def test_control_map_extractor_uses_cv2():
    src = inspect.getsource(control_map_extractor)
    assert "import cv2" in src
    assert "cv2.Canny(" in src, \
        "control_map_extractor no longer calls cv2.Canny — Phase C regressed"


def test_control_map_extractor_dispatches_cv2_provider():
    src = inspect.getsource(control_map_extractor.extract_control_maps)
    assert 'provider == "cv2"' in src, \
        "extract_control_maps no longer routes 'cv2' provider — Phase C regressed"


def test_retry_strategy_defaults_doubao_and_cv2():
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert sig.parameters["anchor_provider"].default == "doubao"
    assert sig.parameters["control_map_provider"].default == "cv2"
