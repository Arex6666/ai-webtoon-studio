"""Auto-import every tool module so registration runs at import time.

Adding a new tool:
1. Create a new .py file in this directory exporting a `tool: ToolDefinition`.
2. Add an import below.
3. Update tests/unit/services/agent/test_builtin_tools_registered.py if changing the v1 catalog.
"""
from app.services.agent.tool_registry import TOOL_REGISTRY

# Query tools
from app.services.agent.tools import query_assets        # noqa: F401
from app.services.agent.tools import query_episodes      # noqa: F401
from app.services.agent.tools import query_panels        # noqa: F401

# Script tools
from app.services.agent.tools import generate_script     # noqa: F401
from app.services.agent.tools import refine_script       # noqa: F401
from app.services.agent.tools import analyze_script      # noqa: F401

# Panel/asset tools (batch 3)
# from app.services.agent.tools import generate_panels
# from app.services.agent.tools import regenerate_asset_image
# from app.services.agent.tools import create_character
# from app.services.agent.tools import create_scene

# Render/QA tools (batch 4)
# from app.services.agent.tools import render_panels
# from app.services.agent.tools import analyze_quality
# from app.services.agent.tools import suggest_fixes

# Studio commit (batch 5)
# from app.services.agent.tools import commit_to_studio

# Panel updates (batch 5)
# from app.services.agent.tools import update_panel_dialogue
# from app.services.agent.tools import update_panel_camera

__all__ = ["TOOL_REGISTRY"]
