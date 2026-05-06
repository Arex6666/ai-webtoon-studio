import pytest
from pathlib import Path

from app.services.agent.skills.manifest import parse_manifest, validate_external_safety, ManifestError


def _write(tmp_path, contents):
    (tmp_path / "skill.yaml").write_text(contents, encoding="utf-8")
    return tmp_path


def test_parse_minimal(tmp_path):
    _write(tmp_path, """
name: foo
version: 1.0.0
description: bar
""")
    m = parse_manifest(tmp_path)
    assert m.name == "foo"
    assert m.version == "1.0.0"
    assert m.guidance is None
    assert m.tools == []
    assert m.mcp_server is None


def test_parse_full(tmp_path):
    _write(tmp_path, """
name: foo
version: 1.0.0
description: d
author: me
activation:
  intent_keywords: [a, b]
  context_required: [project_id]
provides:
  guidance: SKILL.md
  mcp_server:
    transport: stdio
    command: node
    args: [bin/server.js]
    env: {LOG_LEVEL: warn}
""")
    m = parse_manifest(tmp_path)
    assert m.guidance.file == "SKILL.md"
    assert m.mcp_server.transport == "stdio"
    assert m.mcp_server.command == "node"
    assert m.activation.intent_keywords == ["a", "b"]


def test_missing_required_raises(tmp_path):
    _write(tmp_path, "name: foo\n")
    with pytest.raises(ManifestError, match="version"):
        parse_manifest(tmp_path)


def test_external_safety_rejects_tools_bundled(tmp_path):
    _write(tmp_path, """
name: bad
version: 1.0.0
description: d
provides:
  tools:
    - name: x
      handler: m:f
""")
    m = parse_manifest(tmp_path)
    with pytest.raises(ManifestError, match="MCP server"):
        validate_external_safety(m)


def test_external_safety_allows_markdown_only(tmp_path):
    _write(tmp_path, """
name: ok
version: 1.0.0
description: d
provides:
  guidance: SKILL.md
""")
    m = parse_manifest(tmp_path)
    validate_external_safety(m)  # no raise
