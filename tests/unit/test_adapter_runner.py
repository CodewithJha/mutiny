"""M2: TargetAdapter port + conversation runner (Core)."""

from __future__ import annotations

import pytest

from mutiny_core.adapter import (
    TargetAdapter,
    ToolsNotObservableError,
    execute_conversation,
)
from mutiny_core.trace import AdapterTurnResult, ToolCall


class _RecordingAdapter(TargetAdapter):
    """Minimal fake target for runner tests."""

    def __init__(self) -> None:
        self.resets: list[str] = []
        self.steps: list[tuple[str, str]] = []
        self._ctx = {"customer": {"email": "alice@example.com"}}

    def reset(self, session_id: str) -> None:
        self.resets.append(session_id)

    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        self.steps.append((session_id, user_message))
        return AdapterTurnResult(
            assistant_message=f"ack:{user_message}",
            tool_calls=[
                ToolCall(
                    id=f"tc-{len(self.steps)}",
                    name="issue_refund",
                    arguments={
                        "order_id": "ord_1001",
                        "amount": 50,
                        "approved": False,
                    },
                )
            ],
            tool_results=[{"ok": True}],
        )

    def context(self, session_id: str | None = None) -> dict:
        return dict(self._ctx)


class _BlindAdapter(TargetAdapter):
    """Adapter that cannot observe tools — must fail loudly."""

    def reset(self, session_id: str) -> None:
        return None

    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        raise ToolsNotObservableError(
            "tools cannot be observed for this target"
        )

    def context(self, session_id: str | None = None) -> dict:
        return {}


def test_execute_conversation_resets_then_steps():
    adapter = _RecordingAdapter()
    trace = execute_conversation(
        adapter,
        ["hello", "refund please"],
        candidate_id="cand-1",
        session_id="sess-1",
    )
    assert adapter.resets == ["sess-1"]
    assert [m for _, m in adapter.steps] == ["hello", "refund please"]
    assert trace.candidate_id == "cand-1"
    assert trace.session_id == "sess-1"
    assert len(trace.turns) == 2
    assert len(trace.all_tool_calls) == 2
    assert trace.all_tool_calls[0].name == "issue_refund"
    assert trace.all_tool_calls[0].arguments["amount"] == 50
    assert trace.status == "scored"
    assert trace.turns[0].user_message == "hello"
    assert trace.turns[0].assistant_message == "ack:hello"


def test_execute_conversation_empty_messages():
    adapter = _RecordingAdapter()
    trace = execute_conversation(
        adapter, [], candidate_id="c", session_id="s"
    )
    assert adapter.resets == ["s"]
    assert adapter.steps == []
    assert trace.turns == []
    assert trace.all_tool_calls == []
    assert trace.status == "scored"


def test_tools_not_observable_fails_trace():
    adapter = _BlindAdapter()
    with pytest.raises(ToolsNotObservableError):
        execute_conversation(
            adapter, ["hi"], candidate_id="c", session_id="s"
        )


def test_target_adapter_is_abstract():
    with pytest.raises(TypeError):
        TargetAdapter()  # type: ignore[abstract]
