"""Execution traces and tool-call evidence payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """One tool invocation observed from the target agent."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TraceTurn(BaseModel):
    """One conversation turn during candidate execution."""

    user_message: str | None = None
    assistant_message: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] | None = None


class AdapterTurnResult(BaseModel):
    """Result of a single adapter.step call."""

    assistant_message: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """Full candidate execution evidence. Persistence is API-owned.

    ``policy_hits`` stores ``PolicyHit`` objects (from ``mutiny_core.policy``)
    after evaluation; typed loosely here to keep trace free of policy imports.
    """

    candidate_id: str
    session_id: str
    turns: list[TraceTurn] = Field(default_factory=list)
    all_tool_calls: list[ToolCall] = Field(default_factory=list)
    policy_hits: list[Any] = Field(default_factory=list)
    fitness: float | None = None
    status: Literal[
        "created",
        "executing",
        "scored",
        "error",
        "violator",
        "minimized",
    ] = "created"
    error: str | None = None
    model_info: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
