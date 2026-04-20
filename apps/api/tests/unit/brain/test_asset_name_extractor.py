"""
资产名称提取与清洗单元测试
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.services.asset_name_extractor import (
    extract_asset_names_from_panels,
    sanitize_character_names,
    sanitize_scene_names,
)
from app.services.brain.scene_resolver import SceneResolver


def test_sanitize_character_names_filters_placeholder_and_fragments():
    raw_names = [
        "林知夏",
        "角色A",
        "她说",
        "周屿、陈爷爷",
        "人物1",
        "傍晚时分",
    ]

    assert sanitize_character_names(raw_names) == ["林知夏", "周屿", "陈爷爷"]


def test_sanitize_scene_names_merges_verbose_variants():
    raw_scenes = [
        "傍晚时分，杂货铺柜台前，光线昏暗",
        "杂货铺门口",
        "夜晚的杂货铺内",
    ]

    assert sanitize_scene_names(raw_scenes) == ["杂货铺"]


def test_extract_asset_names_from_panels_returns_clean_unique_names():
    panels = [
        {
            "characters": [{"name": "周屿"}, {"name": "角色B"}],
            "scene": {"location": "夜晚，旧书店门口，街灯微亮"},
        },
        {
            "characters": ["林知夏、周屿", "她说"],
            "scene": {"location": "旧书店内"},
        },
    ]

    characters, scenes = extract_asset_names_from_panels(panels)
    assert characters == ["周屿", "林知夏"]
    assert scenes == ["旧书店"]


def test_scene_resolver_handles_leading_punctuation_after_time_strip():
    resolver = SceneResolver(llm_service=object())
    parsed = resolver.parse_scene_description("傍晚时分，杂货铺柜台前，光线昏暗")

    assert parsed["base_location"] == "杂货铺"
    assert parsed["sub_location"] == "柜台前"

