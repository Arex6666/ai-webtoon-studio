"""SkillManifest — typed representation of skill.yaml + validation."""
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import yaml


class ManifestError(ValueError):
    """Raised on invalid manifest."""


@dataclass(frozen=True)
class GuidanceSpec:
    file: str   # path relative to skill root


@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: str           # "module.path:function_name"
    schema: dict
    expected_duration: str = "fast"
    read_only: bool = False


@dataclass(frozen=True)
class McpServerSpec:
    transport: str          # stdio | sse | streamable_http
    command: Optional[str] = None
    args: list[str] = field(default_factory=list)
    url: Optional[str] = None
    env: dict[str, str] = field(default_factory=dict)
    auto_start: bool = True


@dataclass(frozen=True)
class ActivationSpec:
    intent_keywords: list[str] = field(default_factory=list)
    context_required: list[str] = field(default_factory=list)
    context_optional: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str
    description: str
    author: str = ""
    license: str = ""
    homepage: str = ""

    activation: ActivationSpec = field(default_factory=ActivationSpec)
    guidance: Optional[GuidanceSpec] = None
    tools: list[ToolSpec] = field(default_factory=list)
    mcp_server: Optional[McpServerSpec] = None

    requires_min_version: Optional[str] = None
    requires_python: Optional[str] = None

    scope_default: str = "project"

    def has_tools_bundled(self) -> bool:
        return len(self.tools) > 0


def parse_manifest(skill_root: Path) -> SkillManifest:
    """Parse skill.yaml at given root. Raises ManifestError on invalid input."""
    manifest_path = skill_root / "skill.yaml"
    if not manifest_path.exists():
        raise ManifestError(f"skill.yaml not found at {manifest_path}")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ManifestError("skill.yaml must be a mapping at top level")

    for required in ("name", "version", "description"):
        if required not in raw:
            raise ManifestError(f"skill.yaml missing required field: {required}")

    provides = raw.get("provides", {}) or {}
    activation = raw.get("activation", {}) or {}
    requires = raw.get("requires", {}) or {}

    guidance = None
    if "guidance" in provides:
        g = provides["guidance"]
        if isinstance(g, str):
            guidance = GuidanceSpec(file=g)
        elif isinstance(g, dict):
            guidance = GuidanceSpec(file=g["file"])
        else:
            raise ManifestError("provides.guidance must be a string or {file: ...}")

    tools = []
    for t in provides.get("tools", []) or []:
        tools.append(ToolSpec(
            name=t["name"], handler=t["handler"], schema=t.get("schema", {}),
            expected_duration=t.get("expected_duration", "fast"),
            read_only=bool(t.get("read_only", False)),
        ))

    mcp = None
    if provides.get("mcp_server"):
        m = provides["mcp_server"]
        mcp = McpServerSpec(
            transport=m["transport"],
            command=m.get("command"),
            args=list(m.get("args", []) or []),
            url=m.get("url"),
            env=dict(m.get("env", {}) or {}),
            auto_start=bool(m.get("auto_start", True)),
        )

    return SkillManifest(
        name=raw["name"], version=raw["version"], description=raw["description"],
        author=raw.get("author", ""), license=raw.get("license", ""), homepage=raw.get("homepage", ""),
        activation=ActivationSpec(
            intent_keywords=list(activation.get("intent_keywords", []) or []),
            context_required=list(activation.get("context_required", []) or []),
            context_optional=list(activation.get("context_optional", []) or []),
        ),
        guidance=guidance,
        tools=tools,
        mcp_server=mcp,
        requires_min_version=requires.get("webtoon_studio_min_version"),
        requires_python=requires.get("python"),
        scope_default=raw.get("scope_default", "project"),
    )


def validate_external_safety(manifest: SkillManifest) -> None:
    """Reject manifests that violate v1 external-skill policy.

    External skills must be markdown-only or mcp-wrapped. tools-bundled is
    only allowed for builtin skills.
    """
    if manifest.has_tools_bundled():
        raise ManifestError(
            f"Skill '{manifest.name}' bundles Python tool handlers (provides.tools). "
            "v1 only allows tool-bundled skills as built-in (in apps/api/skills/). "
            "External skills must wrap tool capabilities in an MCP server."
        )
