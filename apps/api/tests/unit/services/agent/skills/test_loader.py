import pytest
import sys
from pathlib import Path
from datetime import datetime

from app.services.agent.skills import loader
from app.services.agent.skills.manifest import parse_manifest


def test_load_builtin_skill_with_guidance(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        "name: test\nversion: 1.0.0\ndescription: t\nprovides:\n  guidance: SKILL.md\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text("# Test guidance", encoding="utf-8")

    manifest = parse_manifest(skill_dir)
    loader._load_skill_into_registry("install-1", manifest, skill_dir, is_builtin=True)
    loaded = loader.get_loaded("install-1")
    assert loaded is not None
    assert loaded.guidance_text == "# Test guidance"
    loader.unload_skill("install-1")
    assert loader.get_loaded("install-1") is None


def test_unload_removes_tools(tmp_path):
    skill_dir = tmp_path / "tooled"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("""
name: tooled
version: 1.0.0
description: d
provides:
  tools:
    - name: greet
      handler: greet_module:greet
      schema: {type: object, properties: {}}
      expected_duration: fast
      read_only: true
""", encoding="utf-8")
    (skill_dir / "greet_module.py").write_text(
        "async def greet(args, context, db, tracer):\n    return {'hi': True}\n",
        encoding="utf-8",
    )

    manifest = parse_manifest(skill_dir)
    from app.services.agent.tool_registry import TOOL_REGISTRY
    TOOL_REGISTRY.clear()
    # Clean tool-package modules so registry isn't repopulated mid-test
    for mod in list(sys.modules):
        if mod.startswith("app.services.agent.tools"):
            sys.modules.pop(mod, None)
    loader._load_skill_into_registry("inst-2", manifest, skill_dir, is_builtin=True)
    assert "greet" in TOOL_REGISTRY.names()
    loader.unload_skill("inst-2")
    assert "greet" not in TOOL_REGISTRY.names()
