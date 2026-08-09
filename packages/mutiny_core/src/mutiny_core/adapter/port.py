"""TargetAdapter ABC — ARCHITECTURE §5 / SYSTEM_DESIGN §3."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mutiny_core.trace.models import AdapterTurnResult


class ToolsNotObservableError(RuntimeError):
    """Raised when a target cannot expose tool calls for evidence.

    Campaigns must fail loudly — never invent synthetic tool calls.
    """


class TargetAdapter(ABC):
    """Port for driving a tool-using agent and observing tool calls."""

    @abstractmethod
    def reset(self, session_id: str) -> None:
        """Start or reset a conversation session."""

    @abstractmethod
    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        """Send one user message; return assistant output + observed tool calls.

        Implementations must raise ``ToolsNotObservableError`` if tool
        invocations cannot be captured.
        """

    @abstractmethod
    def context(self, session_id: str | None = None) -> dict[str, Any]:
        """Return deterministic facts for policy evaluation (e.g. customer.email)."""
