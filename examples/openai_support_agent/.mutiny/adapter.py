"""Mutiny adapter wiring for the Acme Support sample project.

Loaded by Local CLI via ``create_adapter()``. With ``--hosted``, execution
stays local and Hosted observes redacted results through ingest.
"""

from __future__ import annotations

from mutiny_openai_agents import OpenAIAgentsAdapter


def create_adapter(*, enforce_refund_policy: bool = False) -> OpenAIAgentsAdapter:
    """Factory used by local ``mutiny run`` and ``mutiny test``.

    ``enforce_refund_policy=True`` is the regression PASS / fixed-agent path.
    """
    from agent import build_agent
    from tools import CUSTOMER_CONTEXT, reset_tool_state

    return OpenAIAgentsAdapter(
        agent=build_agent(enforce_refund_policy=enforce_refund_policy),
        context=CUSTOMER_CONTEXT,
        on_reset=reset_tool_state,
    )
