"""End-to-end: enqueue_scene_anchor_generation with mocked Seedream + real cv2 + in-memory storage.

Verifies the full pipeline: spec → anchor (Seedream mock) → cv2 canny → AnchorStorage uploads.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — register all models
from app.models.base import Base
from app.models.asset import Asset, AssetType
from tests.unit.services.scene._helpers import make_grayscale_gradient_png


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.mark.asyncio
async def test_anchor_e2e_doubao_then_canny(db_session):
    """End-to-end: anchor generated via mocked Seedream, canny extracted via real cv2,
    Asset.data_json updated with both paths."""
    project_id = "test-project"
    scene_id = "scene-1"

    asset = Asset(
        id=scene_id,
        project_id=project_id,
        name="forest",
        type=AssetType.SCENE if hasattr(AssetType, "SCENE") else "scene",
        description="enchanted forest",
        data_json={},
    )
    db_session.add(asset)
    db_session.commit()

    in_memory: dict[str, bytes] = {}

    def make_fake_storage():
        s = MagicMock()
        s._storage = MagicMock()

        async def save_anchor(scene_id, anchor_image, control_maps, metadata=None):
            anchor_path = f"anchors/scenes/{scene_id}/anchor.png"
            in_memory[anchor_path] = anchor_image
            return {"anchor": anchor_path}

        async def load_anchor_image(scene_id):
            return in_memory.get(f"anchors/scenes/{scene_id}/anchor.png")

        async def save_control_map(scene_id, map_type, data):
            path = f"anchors/scenes/{scene_id}/{map_type}.png"
            in_memory[path] = data
            return path

        s.save_anchor = save_anchor
        s.load_anchor_image = load_anchor_image
        s.save_control_map = save_control_map
        s.get_anchor_url = MagicMock(return_value="http://test/anchor.png")
        return s

    fake_storage = make_fake_storage()

    fake_provider = MagicMock()
    fake_provider.api_key = "test-key"
    fake_provider.generate = AsyncMock(return_value=MagicMock(
        success=True,
        image_data=make_grayscale_gradient_png(64, 64),
        image_url="images/test.jpg",
        error=None,
    ))

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_storage), \
         patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider):

        from app.services.scene.retry_strategy import enqueue_scene_anchor_generation

        result = await enqueue_scene_anchor_generation(
            scene_id=scene_id,
            project_id=project_id,
            scene_name="forest",
            location="enchanted forest",
            time_of_day="day",
            mood="calm",
            db_session=db_session,
        )

    assert result["success"] is True, f"flow failed: {result.get('error')}"
    assert result["anchor_path"] == f"anchors/scenes/{scene_id}/anchor.png"
    assert result["control_maps"]["canny"] == f"anchors/scenes/{scene_id}/canny.png"

    assert f"anchors/scenes/{scene_id}/anchor.png" in in_memory
    assert f"anchors/scenes/{scene_id}/canny.png" in in_memory
    canny_bytes = in_memory[f"anchors/scenes/{scene_id}/canny.png"]
    assert canny_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    db_session.refresh(asset)
    data = asset.data_json
    assert data["anchor_status"] == "ready"
    assert data["control_map_status"] == "ready"
    assert data["control_maps"]["canny"] == f"anchors/scenes/{scene_id}/canny.png"
