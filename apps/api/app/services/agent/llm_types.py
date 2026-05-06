"""LLM-provider-agnostic types — shared by provider adapters and runner."""
from dataclasses import dataclass, field
from typing import Literal, Any


@dataclass(frozen=True)
class ToolCallSpec:
    """One tool invocation request from the LLM."""
    id: str           # provider-supplied tool_call_id (used to match results back)
    name: str         # tool name
    arguments: dict   # parsed JSON args


@dataclass(frozen=True)
class LLMMessage:
    """Provider-agnostic message — converted to provider format inside the adapter."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict] = ""    # str for simple; list[dict] for multimodal blocks
    tool_calls: list[ToolCallSpec] | None = None    # role="assistant" only
    tool_call_id: str | None = None                  # role="tool" only
    name: str | None = None                          # role="tool" — tool name


@dataclass(frozen=True)
class StreamChunk:
    """One unit of streamed output from an LLM provider."""
    type: Literal["content_delta", "tool_call_start", "tool_call_delta",
                  "tool_call_done", "stop"]
    delta: str | None = None
    tool_call_index: int | None = None
    tool_call: ToolCallSpec | None = None
    stop_reason: str | None = None
    usage: dict | None = None    # {"input_tokens": N, "output_tokens": N, "cache_hit": bool}
