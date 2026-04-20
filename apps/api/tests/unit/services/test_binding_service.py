"""Unit tests for the pure apply_panel_binding function."""
import pytest

from app.services.binding.binding_service import apply_panel_binding


class TestApplyPanelBinding:
    def test_character_string_to_dict(self):
        spec = {"characters": ["Alice"]}
        out = apply_panel_binding(spec, "character", 0, "asset-1", None)
        assert out["characters"][0] == {"name": "Alice", "asset_id": "asset-1"}

    def test_character_dict_merge(self):
        spec = {"characters": [{"name": "Alice", "emotion": "happy"}]}
        out = apply_panel_binding(spec, "character", 0, "asset-1", "ver-9")
        assert out["characters"][0] == {
            "name": "Alice",
            "emotion": "happy",
            "asset_id": "asset-1",
            "asset_version_id": "ver-9",
        }

    def test_character_rebind_clears_stale_version(self):
        """Rebinding with asset_version_id=None must drop the prior version pin."""
        spec = {"characters": [{"name": "Alice", "asset_id": "asset-1", "asset_version_id": "v1"}]}
        out = apply_panel_binding(spec, "character", 0, "asset-2", None)
        assert out["characters"][0] == {
            "name": "Alice",
            "asset_id": "asset-2",
        }
        assert "asset_version_id" not in out["characters"][0]

    def test_character_clear(self):
        spec = {"characters": [{"name": "Alice", "asset_id": "asset-1", "asset_version_id": "v"}]}
        out = apply_panel_binding(spec, "character", 0, None, None)
        assert out["characters"][0] == {"name": "Alice"}

    def test_character_extends_list(self):
        spec = {"characters": []}
        out = apply_panel_binding(spec, "character", 2, "asset-x", None)
        assert len(out["characters"]) == 3
        assert out["characters"][2] == {"asset_id": "asset-x"}

    def test_scene_sets_anchor(self):
        spec = {"scene": {"location": "rooftop"}}
        out = apply_panel_binding(spec, "scene", 0, "scene-1", None)
        assert out["scene"] == {"location": "rooftop", "anchor_id": "scene-1"}

    def test_scene_clear_anchor(self):
        spec = {"scene": {"location": "rooftop", "anchor_id": "scene-1"}}
        out = apply_panel_binding(spec, "scene", 0, None, None)
        assert out["scene"] == {"location": "rooftop"}

    def test_prop_binding(self):
        spec = {"props": [{"name": "sword"}]}
        out = apply_panel_binding(spec, "prop", 0, "prop-1", None)
        assert out["props"][0] == {"name": "sword", "asset_id": "prop-1"}

    def test_unknown_slot_raises(self):
        with pytest.raises(ValueError):
            apply_panel_binding({}, "bogus", 0, "a", None)

    def test_does_not_mutate_input(self):
        spec = {"characters": [{"name": "Alice"}]}
        _ = apply_panel_binding(spec, "character", 0, "asset-1", None)
        assert spec == {"characters": [{"name": "Alice"}]}
