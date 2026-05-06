"""SkillMatcher — eager-with-cap activation strategy (spec §9 §6).

Score every active skill against (intent, context); concatenate SKILL.md bodies
in score order until SKILL_GUIDANCE_TOKEN_CAP is reached.
"""
from typing import Optional

from app.core.config import settings
from app.services.agent.skills.loader import list_loaded, LoadedSkill


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token. Sufficient for budget tracking."""
    return max(1, len(text) // 4)


def score_skill(skill: LoadedSkill, message: str, context: dict) -> int:
    """Compute activation score per spec §9 (eager-with-cap)."""
    s = 0
    msg_lower = (message or "").lower()
    for kw in skill.manifest.activation.intent_keywords:
        if kw.lower() in msg_lower:
            s += 10
    if skill.manifest.activation.context_required:
        if all(k in context and context[k] is not None for k in skill.manifest.activation.context_required):
            s += 5
        else:
            return 0   # missing required context → not eligible
    for k in skill.manifest.activation.context_optional:
        if k in context and context[k] is not None:
            s += 1
    return s


def pack_guidance(message: str, context: dict, cap_tokens: Optional[int] = None) -> str:
    """Return the concatenated guidance string for prompt injection.

    Empty if no skill has guidance or scores 0.
    """
    cap = cap_tokens or settings.SKILL_GUIDANCE_TOKEN_CAP
    candidates = []
    for skill in list_loaded():
        if not skill.guidance_text:
            continue
        s = score_skill(skill, message, context)
        if s <= 0:
            continue
        candidates.append((s, skill))
    candidates.sort(key=lambda x: (-x[0], x[1].manifest.name))   # score desc, name asc

    parts: list[str] = []
    used = 0
    for _, skill in candidates:
        block = f'<skill name="{skill.manifest.name}">\n{skill.guidance_text}\n</skill>'
        cost = estimate_tokens(block)
        if used + cost > cap:
            break
        parts.append(block)
        used += cost
    return "\n\n".join(parts)
