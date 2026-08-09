"""InProcessDemoAdapter — TargetAdapter wired to DemoSupportAgent."""

from __future__ import annotations

from typing import Any

from mutiny_core.adapter.port import TargetAdapter
from mutiny_core.trace.models import AdapterTurnResult

from demo_agent.agent import DemoSupportAgent
from demo_agent.context import DEMO_CONTEXT


class InProcessDemoAdapter(TargetAdapter):
    """In-process adapter: tool calls are always observable."""

    def __init__(self, agent: DemoSupportAgent | None = None) -> None:
        self.agent = agent or DemoSupportAgent()
        self._sessions: dict[str, bool] = {}

    def reset(self, session_id: str) -> None:
        self.agent.reset()
        self._sessions[session_id] = True

    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        if session_id not in self._sessions:
            # Auto-reset unknown sessions for convenience
            self.reset(session_id)
        out = self.agent.handle_user_message(user_message)
        return AdapterTurnResult(
            assistant_message=out["assistant_message"],
            tool_calls=list(out["tool_calls"]),
            tool_results=list(out["tool_results"]),
            raw={"session_id": session_id, "mode": "in_process_demo"},
        )

    def context(self, session_id: str | None = None) -> dict[str, Any]:
        # Deterministic facts — deep copy so callers cannot mutate shared state
        import copy

        _ = session_id  # context is global for the demo target
        return copy.deepcopy(DEMO_CONTEXT)
