"""Map OpenAI Agents SDK RunResult items → Mutiny ToolCall / messages.

All OpenAI Agents SDK imports stay here (and in adapter.py) — never in Core.
"""

from __future__ import annotations

import json
from typing import Any

from agents import ItemHelpers
from agents.items import MessageOutputItem, ToolCallItem, ToolCallOutputItem
from agents.result import RunResultBase

from mutiny_core.trace.models import ToolCall


def extract_assistant_message(result: RunResultBase) -> str | None:
    """Best-effort assistant text from a run result."""
    if result.final_output is not None:
        out = result.final_output
        if isinstance(out, str):
            return out
        return str(out)
    try:
        text = ItemHelpers.text_message_outputs(list(result.new_items))
    except Exception:  # noqa: BLE001
        text = ""
    return text or None


def extract_tool_calls(result: RunResultBase) -> list[ToolCall]:
    """Collect function/tool calls observed during the run."""
    calls: list[ToolCall] = []
    for item in result.new_items:
        if not _is_tool_call_item(item):
            continue
        name = getattr(item, "tool_name", None) or _raw_name(
            getattr(item, "raw_item", None)
        )
        if not name:
            continue
        call_id = getattr(item, "call_id", None) or f"oa-tc-{len(calls) + 1}"
        arguments = _parse_arguments(getattr(item, "raw_item", None))
        calls.append(ToolCall(id=str(call_id), name=name, arguments=arguments))
    return calls


def extract_tool_results(result: RunResultBase) -> list[dict[str, Any]]:
    """Collect tool outputs paired with call ids when available."""
    results: list[dict[str, Any]] = []
    for item in result.new_items:
        if not _is_tool_output_item(item):
            continue
        payload: dict[str, Any] = {
            "call_id": getattr(item, "call_id", None),
            "output": _normalize_output(getattr(item, "output", None)),
        }
        results.append(payload)
    return results


def tools_observable(result: RunResultBase) -> bool:
    """True if this run path can surface tool call evidence.

    Empty tool_calls is fine (agent may not call tools). We fail only when
    the result object lacks the observation surfaces Mutiny requires.
    """
    return hasattr(result, "new_items")


def summarize_items(result: RunResultBase) -> list[str]:
    """Debug helper: item type names from the run."""
    names: list[str] = []
    for item in result.new_items:
        if _is_tool_call_item(item):
            names.append(f"tool_call:{getattr(item, 'tool_name', None)}")
        elif _is_tool_output_item(item):
            names.append(f"tool_output:{getattr(item, 'call_id', None)}")
        elif isinstance(item, MessageOutputItem) or getattr(
            item, "type", None
        ) == "message_output_item":
            names.append("message")
        else:
            names.append(type(item).__name__)
    return names


def _is_tool_call_item(item: Any) -> bool:
    if isinstance(item, ToolCallItem):
        return True
    return getattr(item, "type", None) == "tool_call_item"


def _is_tool_output_item(item: Any) -> bool:
    if isinstance(item, ToolCallOutputItem):
        return True
    return getattr(item, "type", None) == "tool_call_output_item"


def _raw_name(raw_item: Any) -> str | None:
    if raw_item is None:
        return None
    if isinstance(raw_item, dict):
        name = raw_item.get("name")
        return str(name) if name else None
    name = getattr(raw_item, "name", None)
    return str(name) if name else None


def _parse_arguments(raw_item: Any) -> dict[str, Any]:
    if raw_item is None:
        return {}
    raw_args: Any
    if isinstance(raw_item, dict):
        raw_args = raw_item.get("arguments", {})
    else:
        raw_args = getattr(raw_item, "arguments", {})
    if raw_args is None:
        return {}
    if isinstance(raw_args, dict):
        return dict(raw_args)
    if isinstance(raw_args, str):
        if not raw_args.strip():
            return {}
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            return {"_raw": raw_args}
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    return {"value": raw_args}


def _normalize_output(output: Any) -> Any:
    if isinstance(output, (dict, list, str, int, float, bool)) or output is None:
        return output
    if hasattr(output, "model_dump"):
        try:
            return output.model_dump()
        except Exception:  # noqa: BLE001
            return str(output)
    return str(output)
