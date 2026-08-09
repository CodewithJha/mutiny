"""OpenAI Agents SDK adapter — Mutiny Adapter #1 (ADR-018)."""

from mutiny_openai_agents.adapter import OpenAIAgentsAdapter
from mutiny_openai_agents.loader import load_agent_from_ref, load_callable
from mutiny_openai_agents.sample import make_openai_support_adapter

__all__ = [
    "OpenAIAgentsAdapter",
    "load_agent_from_ref",
    "load_callable",
    "make_openai_support_adapter",
]
