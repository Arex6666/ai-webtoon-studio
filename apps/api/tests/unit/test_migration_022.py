"""Static-source regression for migration 022 (B-1 Phase A schema additions).

Imports the migration module by file path (digit-prefixed filenames aren't
valid Python identifiers) and asserts the upgrade body covers every schema
change documented in the spec §5.
"""
import importlib.util
import inspect
import pathlib


def _load_migration():
    p = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "migrations" / "versions" / "022_unified_agent_runner.py"
    )
    spec = importlib.util.spec_from_file_location("_m022", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_revision_metadata():
    m = _load_migration()
    assert m.revision == "022_unified_agent_runner"
    assert m.down_revision == "021_panel_preview_key"


def test_upgrade_creates_three_new_tables():
    m = _load_migration()
    src = inspect.getsource(m.upgrade)
    assert '"skill_installations"' in src
    assert '"mcp_server_connections"' in src
    assert '"mcp_access_tokens"' in src


def test_upgrade_alters_three_existing_tables():
    m = _load_migration()
    src = inspect.getsource(m.upgrade)
    assert 'batch_alter_table("conversations")' in src
    assert 'batch_alter_table("conversation_messages")' in src
    assert 'batch_alter_table("conversation_actions")' in src


def test_upgrade_adds_documented_columns():
    m = _load_migration()
    src = inspect.getsource(m.upgrade)
    # Conversation
    assert 'sa.Column("agent_state"' in src
    # ConversationMessage
    assert 'sa.Column("trace_id"' in src
    assert 'sa.Column("finish_reason"' in src
    # ConversationAction
    assert 'sa.Column("skill_id"' in src


def test_downgrade_restores_clean_state():
    m = _load_migration()
    src = inspect.getsource(m.downgrade)
    assert 'drop_table("mcp_access_tokens")' in src
    assert 'drop_table("mcp_server_connections")' in src
    assert 'drop_table("skill_installations")' in src
    assert 'drop_column("agent_state")' in src
