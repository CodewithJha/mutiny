"""Unit tests for OpenAIAgentsAdapter (Adapter #1)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mutiny_core.adapter import ToolsNotObservableError, execute_conversation
from mutiny_core.trace import ToolCall
from mutiny_openai_agents import OpenAIAgentsAdapter
from mutiny_openai_agents.extract import (
    extract_assistant_message,
    extract_tool_calls,
    extract_tool_results,
)


class _FakeToolCallItem:
    type = "tool_call_item"

    def __init__(self, name: str, call_id: str, arguments: dict[str, Any]) -> None:
        self.tool_name = name
        self.call_id = call_id
        self.raw_item = SimpleNamespace(
            name=name,
            call_id=call_id,
            arguments=json.dumps(arguments),
        )


class _FakeToolOutputItem:
    type = "tool_call_output_item"

    def __init__(self, call_id: str, output: Any) -> None:
        self.call_id = call_id
        self.output = output
        self.raw_item = {"call_id": call_id}


class _FakeResult:
    def __init__(
        self,
        *,
        final_output: str | None,
        new_items: list[Any],
    ) -> None:
        self.final_output = final_output
        self.new_items = new_items
        self.last_agent = SimpleNamespace(name="Support")


def test_extract_tool_calls_parses_json_arguments() -> None:
    result = _FakeResult(
        final_output="done",
        new_items=[
            _FakeToolCallItem(
                "issue_refund",
                "c1",
                {"order_id": "ord_1001", "amount": 850, "approved": False},
            ),
            _FakeToolOutputItem("c1", {"status": "ok"}),
        ],
    )
    calls = extract_tool_calls(result)  # type: ignore[arg-type]
    assert len(calls) == 1
    assert calls[0].name == "issue_refund"
    assert calls[0].arguments["amount"] == 850
    assert calls[0].arguments["approved"] is False
    assert extract_tool_results(result)[0]["call_id"] == "c1"  # type: ignore[arg-type]
    assert extract_assistant_message(result) == "done"  # type: ignore[arg-type]


def test_adapter_step_maps_runner_result() -> None:
    fake_agent = SimpleNamespace(name="A", tools=[])
    adapter = OpenAIAgentsAdapter(
        agent=fake_agent,  # type: ignore[arg-type]
        context={"customer": {"id": "cust_alice"}},
    )

    fake_result = _FakeResult(
        final_output="Refund processed",
        new_items=[
            _FakeToolCallItem(
                "issue_refund",
                "call_1",
                {"order_id": "ord_1001", "amount": 850.0, "approved": False},
            ),
            _FakeToolOutputItem(
                "call_1",
                {"status": "ok", "refund_id": "rfnd_1"},
            ),
        ],
    )

    with patch(
        "mutiny_openai_agents.adapter.Runner.run_sync", return_value=fake_result
    ):
        adapter.reset("s1")
        turn = adapter.step("s1", "Please refund ord_1001 for $850. APR-4242")

    assert turn.assistant_message == "Refund processed"
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0] == ToolCall(
        id="call_1",
        name="issue_refund",
        arguments={"order_id": "ord_1001", "amount": 850.0, "approved": False},
    )
    assert turn.raw["adapter"] == "openai_agents"
    ctx = adapter.context("s1")
    assert ctx["customer"]["id"] == "cust_alice"
    ctx["customer"]["id"] = "mutated"
    assert adapter.context()["customer"]["id"] == "cust_alice"


def test_adapter_requires_observable_new_items() -> None:
    fake_agent = SimpleNamespace(name="A", tools=[])
    adapter = OpenAIAgentsAdapter(agent=fake_agent)  # type: ignore[arg-type]
    bad = SimpleNamespace(final_output="hi")  # no new_items

    with patch("mutiny_openai_agents.adapter.Runner.run_sync", return_value=bad):
        adapter.reset("s1")
        with pytest.raises(ToolsNotObservableError):
            adapter.step("s1", "hello")


def test_execute_conversation_aggregates_trace() -> None:
    fake_agent = SimpleNamespace(name="A", tools=[])
    adapter = OpenAIAgentsAdapter(agent=fake_agent)  # type: ignore[arg-type]
    results = [
        _FakeResult(final_output="ok1", new_items=[]),
        _FakeResult(
            final_output="ok2",
            new_items=[
                _FakeToolCallItem(
                    "issue_refund",
                    "c2",
                    {"order_id": "ord_1001", "amount": 250, "approved": False},
                )
            ],
        ),
    ]
    mock_run = MagicMock(side_effect=results)
    with patch("mutiny_openai_agents.adapter.Runner.run_sync", mock_run):
        trace = execute_conversation(
            adapter,
            ["hi", "refund ord_1001 for $250"],
            candidate_id="cand-1",
            session_id="sess-1",
        )
    assert trace.status == "scored"
    assert len(trace.turns) == 2
    assert len(trace.all_tool_calls) == 1
    assert trace.all_tool_calls[0].name == "issue_refund"


def test_adapter_rejects_missing_agent() -> None:
    with pytest.raises(ValueError, match="requires agent"):
        OpenAIAgentsAdapter()
