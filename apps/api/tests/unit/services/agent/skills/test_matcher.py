from unittest.mock import MagicMock

from app.services.agent.skills import matcher
from app.services.agent.skills.manifest import SkillManifest, ActivationSpec


def _fake_skill(name, keywords=None, ctx_required=None, guidance="text"):
    m = SkillManifest(
        name=name, version="1.0", description="",
        activation=ActivationSpec(
            intent_keywords=keywords or [],
            context_required=ctx_required or [],
        ),
    )
    s = MagicMock()
    s.manifest = m
    s.guidance_text = guidance
    return s


def test_score_keyword_hits():
    s = _fake_skill("a", keywords=["render", "panel"])
    assert matcher.score_skill(s, "please render the panel", {}) == 20


def test_score_context_required_satisfied():
    s = _fake_skill("a", ctx_required=["project_id"])
    assert matcher.score_skill(s, "", {"project_id": "p1"}) == 5
    assert matcher.score_skill(s, "", {"project_id": None}) == 0


def test_pack_guidance_respects_cap(monkeypatch):
    s1 = _fake_skill("a", keywords=["x"], guidance="A" * 1000)
    s2 = _fake_skill("b", keywords=["x"], guidance="B" * 1000)
    monkeypatch.setattr(matcher, "list_loaded", lambda: [s1, s2])
    out = matcher.pack_guidance("x", {}, cap_tokens=300)
    assert "<skill name=\"a\">" in out
    assert "<skill name=\"b\">" not in out


def test_pack_guidance_empty_when_no_match(monkeypatch):
    s1 = _fake_skill("a", keywords=["x"])
    monkeypatch.setattr(matcher, "list_loaded", lambda: [s1])
    out = matcher.pack_guidance("unrelated message", {})
    assert out == ""
