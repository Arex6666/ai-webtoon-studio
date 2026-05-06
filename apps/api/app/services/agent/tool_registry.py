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
