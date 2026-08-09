"""OpenAIAgentsAdapter — TargetAdapter for OpenAI Agents SDK projects."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from agents import Agent, Runner
from agents.memory.sqlite_session import SQLiteSession

from mutiny_core.adapter.port import TargetAdapter, ToolsNotObservableError
from mutiny_core.trace.models import AdapterTurnResult

from mutiny_openai_agents.extract import (
    extract_assistant_message,
    extract_tool_calls,
    extract_tool_results,
    summarize_items,
    tools_observable,
)
from mutiny_openai_agents.loader import load_agent_from_ref


class OpenAIAgentsAdapter(TargetAdapter):
    """Drive an OpenAI Agents SDK ``Agent`` and observe tool calls.

    Framework-specific imports stay inside this package (ADR-018). Core only
    sees ``TargetAdapter`` / ``AdapterTurnResult``.
    """

    def __init__(
        self,
        agent: Agent[Any] | None = None,
        *,
        agent_ref: str | None = None,
        agent_factory: Callable[[], Agent[Any]] | None = None,
        context: dict[str, Any] | None = None,
        context_provider: Callable[[], dict[str, Any]] | None = None,
        session_factory: Callable[[str], Any] | None = None,
        on_reset: Callable[[], None] | None = None,
        max_turns: int = 10,
    ) -> None:
        if agent is None and agent_ref is None and agent_factory is None:
            raise ValueError(
                "OpenAIAgentsAdapter requires agent=, agent_ref=, or agent_factory="
            )
        self._agent = agent
        self._agent_ref = agent_ref
        self._agent_factory = agent_factory
        self._context = context or {}
        self._context_provider = context_provider
        self._session_factory = session_factory or (
            lambda sid: SQLiteSession(sid, db_path=":memory:")
        )
        self._on_reset = on_reset
        self._max_turns = max_turns
        self._sessions: dict[str, Any] = {}
        self._resolved_agent: Agent[Any] | None = None

    def reset(self, session_id: str) -> None:
        """Start a fresh conversation session (in-memory SQLite by default)."""
        if self._on_reset is not None:
            self._on_reset()
        previous = self._sessions.pop(session_id, None)
        if previous is not None and hasattr(previous, "close"):
            try:
                previous.close()
            except Exception:  # noqa: BLE001
                pass
        self._sessions[session_id] = self._session_factory(session_id)

    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        """Run one user turn via ``Runner.run_sync``; map tools → Mutiny traces."""
        if session_id not in self._sessions:
            self.reset(session_id)

        agent = self._get_agent()
        session = self._sessions[session_id]

        try:
            result = Runner.run_sync(
                agent,
                user_message,
                session=session,
                max_turns=self._max_turns,
            )
        except ToolsNotObservableError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Surface SDK failures without inventing tool evidence
            raise RuntimeError(
                f"OpenAI Agents SDK run failed for session={session_id}: {exc}"
            ) from exc

        if not tools_observable(result):
            raise ToolsNotObservableError(
                "OpenAI Agents SDK result does not expose new_items; "
                "cannot observe tool calls for policy evidence"
            )

        tool_calls = extract_tool_calls(result)
        tool_results = extract_tool_results(result)
        assistant = extract_assistant_message(result)

        return AdapterTurnResult(
            assistant_message=assistant,
            tool_calls=tool_calls,
            tool_results=tool_results,
            raw={
                "session_id": session_id,
                "adapter": "openai_agents",
                "item_summary": summarize_items(result),
                "last_agent": getattr(
                    getattr(result, "last_agent", None), "name", None
                ),
            },
        )

    def context(self, session_id: str | None = None) -> dict[str, Any]:
        """Deterministic facts for policy evaluation."""
        _ = session_id
        if self._context_provider is not None:
            return copy.deepcopy(self._context_provider())
        return copy.deepcopy(self._context)

    def _get_agent(self) -> Agent[Any]:
        if self._resolved_agent is not None:
            return self._resolved_agent
        if self._agent is not None:
            self._resolved_agent = self._agent
            return self._resolved_agent
        if self._agent_factory is not None:
            self._resolved_agent = self._agent_factory()
            return self._resolved_agent
        assert self._agent_ref is not None
        self._resolved_agent = load_agent_from_ref(self._agent_ref)
        return self._resolved_agent
