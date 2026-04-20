"""Unit tests for agent_commit.spec_builder (pure functions)."""
from app.schemas.agent_commit import AgentPanel, AgentArtStyle
from app.services.agent_commit.spec_builder import build_panel_spec, build_chapter_source


def make_panel(**kw):
    defaults = dict(
        id="agent-panel-1", order=0, scene_name="rooftop",
        characters=["Alice", "Bob"], scene_description="they meet",
        shot_type="MS", camera_angle="eye-level",
    )
    defaults.update(kw)
    return AgentPanel(**defaults)


class TestBuildPanelSpec:
    def test_maps_core_fields(self):
        spec = build_panel_spec(
            make_panel(),
            panel_id="p-uuid",
            character_name_to_id={"Alice": "a-id", "Bob": "b-id"},
            scene_name_to_id={"rooftop": "scene-id"},
            art_style=AgentArtStyle(base_style="Korean webtoon"),
        )
        assert spec["id"] == "p-uuid"
        assert spec["index"] == 0
        assert spec["shot"]["shotType"] == "MS"
        assert spec["scene"]["anchor_id"] == "scene-id"
        assert spec["characters"][0] == {"name": "Alice", "asset_id": "a-id"}
        assert spec["characters"][1] == {"name": "Bob", "asset_id": "b-id"}
        assert spec["meta"]["source"] == "agent"
        assert spec["meta"]["agent_panel_id"] == "agent-panel-1"

    def test_unknown_character_no_asset_id(self):
        spec = build_panel_spec(
            make_panel(characters=["Unknown"]),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert spec["characters"][0] == {"name": "Unknown"}

    def test_scene_without_anchor(self):
        spec = build_panel_spec(
            make_panel(scene_name="nowhere"),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert "anchor_id" not in spec["scene"]

    def test_dialogue_empty_list_when_no_dialogue(self):
        spec = build_panel_spec(
            make_panel(),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert spec["dialogue"]["lines"] == []

    def test_dialogue_line_when_present(self):
        spec = build_panel_spec(
            make_panel(dialogue="hi"),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert spec["dialogue"]["lines"] == [{"speaker": "Unknown", "text": "hi", "type": "speech"}]


class TestBuildChapterSource:
    def test_contains_required_keys(self):
        src = build_chapter_source(
            conversation_id="conv-1", episode_number=3,
            art_style=AgentArtStyle(base_style="X"),
        )
        assert src["type"] == "agent"
        assert src["conversation_id"] == "conv-1"
        assert src["episode_number"] == 3
        assert "committed_at" in src
        assert src["art_style_snapshot"]["base_style"] == "X"
