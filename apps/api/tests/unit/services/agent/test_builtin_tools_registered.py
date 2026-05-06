"""Static-source regression — confirms all 16 v1 built-in tools register at import.

Reference: spec §4 v1 built-in tool catalog (16 tools).
"""


EXPECTED_TOOLS = [
    "query_assets", "query_episodes", "query_panels",
    "generate_script", "refine_script", "analyze_script",
    "generate_panels", "regenerate_asset_image",
    "create_character", "create_scene",
    "render_panels", "analyze_quality", "suggest_fixes",
    "commit_to_studio",
    "update_panel_dialogue", "update_panel_camera",
]


def test_all_v1_builtin_tools_registered():
    # Import the tools package — its __init__.py auto-registers every tool file.
    import app.services.agent.tools  # noqa: F401
    from app.services.agent.tool_registry import TOOL_REGISTRY
    actual = set(TOOL_REGISTRY.names())
    missing = set(EXPECTED_TOOLS) - actual
    assert not missing, f"Tools missing from TOOL_REGISTRY: {sorted(missing)}"
