"""Static-source regression: verify legacy B-1 files don't exist (Phase E)."""
import os.path
import re
import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.parametrize("relpath", [
    "app/services/agents/asset_agent.py",
    "app/services/agents/script_agent.py",
    "app/services/agents/rendering_agent.py",
    "app/services/agents/qa_agent.py",
    "app/services/conversation/agent_orchestrator.py",
    "app/services/conversation/intent_router.py",
    "app/services/conversation/tool_registry.py",
    "app/services/conversation/tool_handlers.py",
    "app/services/orchestrator/studio_orchestrator.py",
    "app/api/routes/orchestrator.py",
])
def test_legacy_file_deleted(relpath: str):
    p = os.path.join(REPO_ROOT, relpath)
    assert not os.path.exists(p), f"legacy file still exists: {relpath}"


def test_no_legacy_imports_remain():
    """Walk app/ and assert no live module imports the deleted classes."""
    forbidden = ["AssetAgent", "ScriptAgent", "RenderingAgent", "QAAgent",
                 "AgentOrchestrator", "IntentRouter", "StudioOrchestrator"]
    pattern = re.compile(r"\b(" + "|".join(forbidden) + r")\b")
    offenders = []
    app_dir = os.path.join(REPO_ROOT, "app")
    for root, _, files in os.walk(app_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            with open(p, encoding="utf-8") as fh:
                src = fh.read()
            for m in pattern.finditer(src):
                # ignore matches inside comments / strings (simplest: ignore line if # or ''' or """)
                line_start = src.rfind("\n", 0, m.start()) + 1
                line_end = src.find("\n", m.end())
                line = src[line_start:line_end if line_end >= 0 else len(src)]
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                offenders.append(f"{p}:{src.count(chr(10), 0, m.start()) + 1}: {line.rstrip()}")
    assert not offenders, "forbidden symbols still referenced:\n" + "\n".join(offenders)
