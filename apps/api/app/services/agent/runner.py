"""AgentRunner — multi-step LLM-driven loop with tool execution.

Orchestrates: load history → call LLM (streaming) → execute tools (parallel reads,
serial writes; slow tools dispatch to Celery and return immediately) → persist
messages and actions → repeat until LLM stops or max_steps hit.

The runner runs as a background asyncio task; SSE dispatch (DISPATCHER) is the
observation channel — a disconnecting client does NOT cancel the loop.

Termination conditions:
- "stop" — LLM emitted no tool calls (natural stop)
- "max_steps" — loop ran max_steps still calling tools
- "user_canceled" — Redis cancel flag detected at step boundary
- "error" — unrecoverable LLMProviderError or other exception

Slow tools: handler returns {"dispatched": {"job_id": ..., "eta_seconds": ...}}.
Loop emits the result back to the LLM as the dispatched dict (LLM treats it
as a tool result; dispatcher pattern keeps LLM informed without blocking).
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.conversation_action import ConversationAction
from app.services.agent.cancellation import is_canceled, clear_cancel
from app.services.agent.llm_provider import get_llm_provider, LLMProviderError
from app.services.agent.llm_types import LLMMessage, ToolCallSpec
from app.services.agent.model_router import MODEL_ROUTER, StepContext
from app.services.agent.skills.matcher import pack_guidance
from app.services.agent.sse import DISPATCHER
from app.services.agent.tool_registry import TOOL_REGISTRY, compute_available_tools, ToolDefinition
from app.services.agent.trace import with_tracer

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are the AI Webtoon Studio assistant. Help the user produce manhua/webtoon content "
    "by combining conversation, planning, and the available tools. Prefer calling tools over "
    "describing actions. When you call a slow tool, respond briefly noting the dispatch and "
    "stop — do not loop. When you have nothing left to do, simply reply without tool calls."
)


class AgentRunner:
    def __init__(self, db: Session):
        self.db = db
        self.provider = get_llm_provider()

    async def run(
        self,
        conversation_id: str,
        user_message: str,
        context: dict,
        options: dict,
    ) -> None:
        """Run a full agent loop for a single user message.

        Persists user message, runs steps until termination, persists assistant
        messages + tool actions, emits SSE events along the way.
        """
        max_steps = int(options.get("max_steps", 10))
        allowlist = options.get("tools_allowlist")
        force_model = options.get("model")

        # Clear any stale cancel flag from a prior loop
        await clear_cancel(conversation_id)

        await DISPATCHER.emit(conversation_id, "conversation_started", {
            "conversation_id": conversation_id,
            "created_new": False,
        })

        # Persist user message
        user_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )
        self.db.add(user_msg)
        self._set_state(conversation_id, "running")
        self.db.commit()

        async with with_tracer(conversation_id=conversation_id) as tracer:
            async with tracer.span("agent_loop", **{
                "webtoon.conversation_id": conversation_id,
                "webtoon.context.project_id": context.get("project_id"),
                "webtoon.context.episode_number": context.get("episode_number"),
            }):
                done_reason = await self._loop(
                    tracer, conversation_id, context, max_steps, allowlist, force_model, user_message,
                )

        self._set_state(conversation_id, self._reason_to_state(done_reason))
        await DISPATCHER.emit(conversation_id, "agent_done", {"reason": done_reason})

    async def _loop(
        self, tracer, conversation_id, context, max_steps, allowlist, force_model, last_user_message,
    ) -> str:
        # Enrich context with the active conversation_id so tool handlers
        # (e.g. commit_to_studio's lean-payload path) can build a
        # CommitToStudioRequest without the runner having to pass a separate
        # arg. Mutating a shallow copy keeps the caller's dict untouched.
        context = {**context, "conversation_id": conversation_id}
        had_tool_results = False
        for step_index in range(max_steps):
            if await is_canceled(conversation_id):
                return "user_canceled"

            async with tracer.span("agent_step", step_index=step_index):
                history = self._load_history(conversation_id)
                tools = compute_available_tools(context, allowlist)
                guidance = pack_guidance(last_user_message, context)

                step_ctx = StepContext(
                    is_first_step=(step_index == 0),
                    has_tool_results=had_tool_results,
                    is_simple_chat=(not tools),
                    user_force_model=force_model,
                )
                model = MODEL_ROUTER.select(step_ctx)

                await DISPATCHER.emit(conversation_id, "agent_step_started", {
                    "step_index": step_index, "model": model,
                })

                try:
                    assistant_text, tool_calls, finish_reason = await self._call_llm(
                        tracer, conversation_id, history, tools, guidance, model,
                    )
                except LLMProviderError as e:
                    logger.exception("LLM call failed")
                    await DISPATCHER.emit(conversation_id, "error", {
                        "code": "LLM_PROVIDER_ERROR", "message": str(e), "recoverable": False,
                    })
                    return "error"
                except Exception as e:
                    logger.exception("Unexpected error in LLM call")
                    await DISPATCHER.emit(conversation_id, "error", {
                        "code": "INTERNAL_ERROR", "message": str(e), "recoverable": False,
                    })
                    return "error"

                # Persist assistant message
                msg = ConversationMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text or "",
                    tool_calls_json=[
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in tool_calls
                    ] if tool_calls else None,
                    finish_reason=finish_reason,
                    trace_id=tracer.trace_id,
                )
                self.db.add(msg)
                self.db.commit()

                if not tool_calls:
                    return "stop"

                results = await self._execute_tools(
                    tracer, conversation_id, tool_calls, context, msg.id,
                )
                had_tool_results = True

                # Insert tool results back into history as role=tool messages so the LLM sees them next step.
                # Persist the tool_call_id + name into tool_calls_json so _load_history can
                # reconstruct the OpenAI-spec required `tool_call_id` field on the LLMMessage —
                # Doubao/OpenAI/etc reject role=tool messages without a tool_call_id.
                for tc, r in zip(tool_calls, results):
                    tool_msg = ConversationMessage(
                        id=str(uuid.uuid4()),
                        conversation_id=conversation_id,
                        role="tool",
                        content=json.dumps(r, ensure_ascii=False, default=str),
                        tool_calls_json=[{"id": tc.id, "name": tc.name}],
                        trace_id=tracer.trace_id,
                    )
                    self.db.add(tool_msg)
                self.db.commit()

                await DISPATCHER.emit(conversation_id, "agent_step_completed", {
                    "step_index": step_index, "tool_calls_emitted": len(tool_calls),
                })

        return "max_steps"

    async def _call_llm(
        self, tracer, conversation_id, history, tools, guidance, model,
    ) -> tuple[str, list[ToolCallSpec], str]:
        """Stream one LLM call, accumulating content + tool calls.

        Returns (assistant_text, tool_calls, finish_reason).
        """
        async with tracer.span("llm_call", **{
            "gen_ai.system": self.provider.name,
            "gen_ai.request.model": model,
        }) as attrs:
            full_system = SYSTEM_PROMPT
            if guidance:
                full_system = SYSTEM_PROMPT + "\n\n" + guidance

            assistant_text = ""
            assembled: dict[int, ToolCallSpec] = {}
            finish_reason = "stop"
            assistant_msg_id = str(uuid.uuid4())

            async for chunk in self.provider.stream(
                system=full_system,
                messages=history,
                tools=tools,
                model=model,
            ):
                if chunk.type == "content_delta" and chunk.delta:
                    assistant_text += chunk.delta
                    await DISPATCHER.emit(conversation_id, "assistant_message_chunk", {
                        "message_id": assistant_msg_id, "delta": chunk.delta,
                    })
                elif chunk.type == "tool_call_done" and chunk.tool_call:
                    idx = chunk.tool_call_index if chunk.tool_call_index is not None else len(assembled)
                    assembled[idx] = chunk.tool_call
                elif chunk.type == "stop":
                    finish_reason = chunk.stop_reason or "stop"
                    if chunk.usage:
                        attrs["gen_ai.usage.input_tokens"] = chunk.usage.get("input_tokens")
                        attrs["gen_ai.usage.output_tokens"] = chunk.usage.get("output_tokens")
                        attrs["gen_ai.cache.hit"] = chunk.usage.get("cache_hit", False)

            tool_calls = [assembled[i] for i in sorted(assembled.keys())]
            if assistant_text:
                await DISPATCHER.emit(conversation_id, "assistant_message_complete", {
                    "message_id": assistant_msg_id,
                    "content": assistant_text,
                    "finish_reason": finish_reason,
                })
            return assistant_text, tool_calls, finish_reason

    async def _execute_tools(
        self, tracer, conversation_id, tool_calls, context, message_id,
    ) -> list[dict]:
        """Execute tool calls — read-only in parallel, writes serially.

        Returns results in the original order (matches tool_calls order).
        """
        read_only_jobs = []
        write_jobs = []
        for tc in tool_calls:
            tool = TOOL_REGISTRY.get(tc.name)
            if tool and tool.read_only:
                read_only_jobs.append((tc, tool))
            else:
                write_jobs.append((tc, tool))

        results_by_id: dict[str, dict] = {}

        async def _run_one(tc, tool):
            r = await self._run_tool(tracer, conversation_id, tc, tool, context, message_id)
            results_by_id[tc.id] = r

        # Parallel read-only
        if read_only_jobs:
            await asyncio.gather(*[_run_one(tc, t) for tc, t in read_only_jobs])

        # Serial writes
        for tc, tool in write_jobs:
            await _run_one(tc, tool)

        # Return in original tool_calls order
        return [results_by_id.get(tc.id, {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "no result"}}) for tc in tool_calls]

    async def _run_tool(self, tracer, conversation_id, tc, tool, context, message_id) -> dict:
        """Execute a single tool, persist a ConversationAction, emit SSE events."""
        action = ConversationAction(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            message_id=message_id,
            action_type=tc.name,
            action_params_json=tc.arguments,
            status="running",
            trace_id=tracer.trace_id,
            skill_id=tool.source_skill_id if tool else None,
        )
        self.db.add(action)
        self.db.commit()

        await DISPATCHER.emit(conversation_id, "tool_call", {
            "action_id": action.id, "tool_name": tc.name,
            "args": tc.arguments,
            "skill_id": tool.source_skill_id if tool else None,
        })
        await DISPATCHER.emit(conversation_id, "tool_executing", {"action_id": action.id})

        if not tool:
            err = {"code": "TOOL_NOT_FOUND", "message": f"Unknown tool: {tc.name}"}
            action.status = "failed"
            action.error_json = err
            self.db.commit()
            await DISPATCHER.emit(conversation_id, "tool_result", {
                "action_id": action.id, "success": False, "error": err,
            })
            return {"success": False, "error": err}

        async with tracer.span("tool_call", **{
            "webtoon.tool.name": tc.name,
            "webtoon.tool.skill_id": tool.source_skill_id,
            "webtoon.tool.read_only": tool.read_only,
        }) as attrs:
            try:
                result = await tool.handler(tc.arguments, context, self.db, tracer)
            except Exception as e:
                logger.exception("Tool %s failed", tc.name)
                err = {"code": "TOOL_EXECUTION_ERROR", "message": repr(e)}
                action.status = "failed"
                action.error_json = err
                self.db.commit()
                await DISPATCHER.emit(conversation_id, "tool_result", {
                    "action_id": action.id, "success": False, "error": err,
                })
                return {"success": False, "error": err}

            dispatched = result.get("dispatched") if isinstance(result, dict) else None
            attrs["webtoon.tool.dispatched"] = bool(dispatched)
            if dispatched:
                action.status = "dispatched"
                action.job_id = dispatched.get("job_id")
                action.result_json = result
            else:
                action.status = "completed"
                action.result_json = result
            self.db.commit()
            await DISPATCHER.emit(conversation_id, "tool_result", {
                "action_id": action.id, "success": True,
                "result": result, "dispatched": dispatched,
            })
            return {"success": True, "result": result}

    def _load_history(self, conversation_id: str) -> list[LLMMessage]:
        """Load conversation history, normalize legacy tool_calls_json shapes."""
        rows = (
            self.db.query(ConversationMessage)
            .filter_by(conversation_id=conversation_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        out: list[LLMMessage] = []
        for r in rows:
            # Tool messages: extract tool_call_id + name from tool_calls_json[0]
            # so the OpenAI-spec required `tool_call_id` survives the round-trip.
            if r.role == "tool":
                tc_meta = (r.tool_calls_json or [{}])[0] if r.tool_calls_json else {}
                out.append(LLMMessage(
                    role="tool",
                    content=r.content or "",
                    tool_call_id=tc_meta.get("id"),
                    name=tc_meta.get("name"),
                ))
                continue

            # Assistant messages with tool_calls — reconstruct ToolCallSpec list
            tool_calls = None
            if r.tool_calls_json:
                tool_calls = []
                for tc in r.tool_calls_json:
                    if "tool_name" in tc:
                        # Legacy shape from pre-B1 chat path
                        tool_calls.append(ToolCallSpec(
                            id=tc.get("id") or str(uuid.uuid4()),
                            name=tc["tool_name"],
                            arguments=tc.get("parameters") or {},
                        ))
                    else:
                        tool_calls.append(ToolCallSpec(
                            id=tc["id"], name=tc["name"], arguments=tc.get("arguments", {}),
                        ))
            out.append(LLMMessage(
                role=r.role,
                content=r.content or "",
                tool_calls=tool_calls,
            ))
        return out

    def _set_state(self, conversation_id: str, state: str) -> None:
        conv = self.db.query(Conversation).filter_by(id=conversation_id).first()
        if conv:
            conv.agent_state = state
            self.db.commit()

    @staticmethod
    def _reason_to_state(reason: str) -> str:
        return {
            "stop": "done",
            "max_steps": "paused",
            "user_canceled": "canceled",
            "error": "error",
        }.get(reason, "idle")
