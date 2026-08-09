"""Mutiny adapter wiring for the Acme Support sample project.

Loaded by Hosted / CLI via ``create_adapter()`` — same path as any customer
OpenAI Agents SDK project.
"""

from __future__ import annotations

from mutiny_openai_agents import OpenAIAgentsAdapter


def create_adapter(*, enforce_refund_policy: bool = False) -> OpenAIAgentsAdapter:
    """Factory used by Hosted and ``mutiny run``.

    ``enforce_refund_policy=True`` is the regression PASS / fixed-agent path.
    """
    from agent import build_agent
    from tools import CUSTOMER_CONTEXT, reset_tool_state

    return OpenAIAgentsAdapter(
        agent=build_agent(enforce_refund_policy=enforce_refund_policy),
        context=CUSTOMER_CONTEXT,
        on_reset=reset_tool_state,
    )
