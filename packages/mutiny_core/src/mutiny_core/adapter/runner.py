"""Single-conversation runner: messages → adapter → ExecutionTrace."""

from __future__ import annotations

import uuid

from mutiny_core.adapter.port import TargetAdapter, ToolsNotObservableError
from mutiny_core.trace.models import ExecutionTrace, TraceTurn


def execute_conversation(
    adapter: TargetAdapter,
    messages: list[str],
    *,
    candidate_id: str,
    session_id: str | None = None,
) -> ExecutionTrace:
    """Reset adapter, step each user message, aggregate an ExecutionTrace.

    Pure orchestration over the ``TargetAdapter`` port. No persistence, no LLM.
    """
    sid = session_id or str(uuid.uuid4())
    trace = ExecutionTrace(
        candidate_id=candidate_id,
        session_id=sid,
        status="executing",
    )

    try:
        adapter.reset(sid)
        for user_message in messages:
            try:
                result = adapter.step(sid, user_message)
            except ToolsNotObservableError:
                raise
            turn = TraceTurn(
                user_message=user_message,
                assistant_message=result.assistant_message,
                tool_calls=list(result.tool_calls),
                tool_results=list(result.tool_results),
                raw=dict(result.raw) if result.raw else None,
            )
            trace.turns.append(turn)
            trace.all_tool_calls.extend(turn.tool_calls)
        trace.status = "scored"
        return trace
    except ToolsNotObservableError as exc:
        trace.status = "error"
        trace.error = str(exc)
        raise
