"""Smoke tests verifying B-1 Phase A new routes register."""
from app.main import app


def test_agent_chat_route():
    paths = {r.path for r in app.routes}
    assert "/v1/agent/chat" in paths


def test_agent_conversations_routes():
    paths = {r.path for r in app.routes}
    assert "/v1/agent/conversations" in paths
    assert "/v1/agent/conversations/{conv_id}" in paths
    assert "/v1/agent/conversations/{conv_id}/messages" in paths
    assert "/v1/agent/conversations/{conv_id}/cancel" in paths


def test_skills_routes():
    paths = {r.path for r in app.routes}
    assert "/v1/skills" in paths
    assert "/v1/skills/install" in paths
    assert "/v1/skills/{skill_id}" in paths
    assert "/v1/skills/{skill_id}/enable" in paths
    assert "/v1/skills/{skill_id}/disable" in paths


def test_mcp_admin_routes():
    paths = {r.path for r in app.routes}
    assert "/v1/mcp/connections" in paths
    assert "/v1/mcp/connections/{conn_id}" in paths
    assert "/v1/mcp/connections/{conn_id}/reconnect" in paths
