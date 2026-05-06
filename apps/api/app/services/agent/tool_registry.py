"""Tool registry — central record of available tools for the agent runner.

Tools are registered at startup (built-in) or dynamically (skills, MCP).
Runner queries via compute_available_tools(context) per loop step.
"""
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any, Literal


@dataclass(frozen=True)
class ToolDefinition:
    """Declarative tool metadata + handler.

    Naming: snake_case for built-in tools (e.g., "render_panels"). External MCP
    tools are prefixed `mcp_{conn_id}_` to avoid collision; the LLM-facing
    `description` should not include this prefix.
    """
    name: str
    description: str
    json_schema: dict
    handler: Callable[..., Awaitable[Any]]
    requires_context: tuple[str, ...] = ()
    expected_duration: Literal["fast", "slow"] = "fast"
    read_only: bool = False
    side_effects: tuple[str, ...] = ()
    source_skill_id: str = "builtin"


def is_visible(tool: ToolDefinition, context: dict) -> bool:
    """Return True iff every key in tool.requires_context is non-None in context."""
    return all(
        k in context and context[k] is not None
        for k in tool.requires_context
    )


class ToolRegistry:
    """Process-wide registry of available tools.

    Built-in tools register at startup via `register()`. External MCP tools
    register dynamically when their server connects (and deregister on
    disconnect). Skills can also register tools they bundle.

    Lookup is by `name`; registration is idempotent on `name` (last-write-wins,
    with a logged warning for any redefinition).
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            import logging
            logging.getLogger(__name__).warning(
                "Tool name collision: %s overwriting existing registration "
                "(prev source: %s, new source: %s)",
                tool.name, self._tools[tool.name].source_skill_id, tool.source_skill_id,
            )
        self._tools[tool.name] = tool

    def deregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def clear(self) -> None:
        """Test-only — wipe all registrations."""
        self._tools.clear()


# Process-wide singleton — accessed via `from app.services.agent.tool_registry import TOOL_REGISTRY`
TOOL_REGISTRY = ToolRegistry()


def compute_available_tools(
    context: dict,
    allowlist: list[str] | None = None,
) -> list[ToolDefinition]:
    """Filter TOOL_REGISTRY by context visibility + optional allowlist.

    Result is sorted by name (deterministic for prompt-cache stability).
    """
    out = []
    for tool in TOOL_REGISTRY.all():
        if not is_visible(tool, context):
            continue
        if allowlist is not None and tool.name not in allowlist:
            continue
        out.append(tool)
    return sorted(out, key=lambda t: t.name)
