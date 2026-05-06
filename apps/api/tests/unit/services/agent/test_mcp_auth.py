from app.services.agent.mcp_auth import is_tool_allowed, is_project_allowed, _hash


def test_hash_is_deterministic():
    assert _hash("abc") == _hash("abc")


def test_hash_differs_for_different_inputs():
    assert _hash("abc") != _hash("abd")


def test_tool_allowlist_exact_match():
    assert is_tool_allowed({"tools": ["render_panels"]}, "render_panels")
    assert not is_tool_allowed({"tools": ["render_panels"]}, "query_assets")


def test_tool_allowlist_wildcard():
    assert is_tool_allowed({"tools": ["query_*"]}, "query_panels")
    assert not is_tool_allowed({"tools": ["query_*"]}, "render_panels")


def test_tool_allowlist_global_star():
    assert is_tool_allowed({"tools": ["*"]}, "anything")


def test_tool_allowlist_empty_means_open():
    assert is_tool_allowed({}, "anything")
    assert is_tool_allowed({"tools": []}, "anything")


def test_project_allowlist():
    assert is_project_allowed({"projects": ["p1"]}, "p1")
    assert not is_project_allowed({"projects": ["p1"]}, "p2")
    assert is_project_allowed({}, "p1")  # no restriction
