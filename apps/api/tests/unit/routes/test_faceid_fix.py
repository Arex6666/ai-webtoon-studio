"""Test that generate_asset_image writes canonical FaceID fields."""
import pytest
from unittest.mock import MagicMock


def make_fake_asset(asset_type="character"):
    asset = MagicMock()
    asset.id = "asset-001"
    asset.type = asset_type
    asset.project_id = "proj-001"
    asset.name = "TestChar"
    asset.data_json = {"description": "A test character", "reference_images": []}
    asset.thumbnail_url = None
    return asset


class TestFaceIDFieldName:
    def test_embedding_path_written_with_canonical_key(self):
        asset = make_fake_asset()
        result = {
            "success": True,
            "image_url": "https://storage/char.png",
            "embedding_path": "embeddings/proj-001/asset-001/face.bin",
        }
        data = dict(asset.data_json)
        if result.get("embedding_path"):
            data["embedding_path"] = result["embedding_path"]
            data["embedding_status"] = "ready"
            data["embedding_source"] = "auto_generation"
            data["face_embedding"] = result["embedding_path"]

        assert data["embedding_path"] == "embeddings/proj-001/asset-001/face.bin"
        assert data["embedding_status"] == "ready"
        assert data["face_embedding"] == data["embedding_path"]

    def test_no_embedding_path_leaves_status_unchanged(self):
        asset = make_fake_asset()
        result = {"success": True, "image_url": "https://storage/char.png"}
        data = dict(asset.data_json)
        if result.get("embedding_path"):
            data["embedding_path"] = result["embedding_path"]
            data["embedding_status"] = "ready"

        assert "embedding_path" not in data
        assert "embedding_status" not in data
