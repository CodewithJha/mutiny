"""Structured mutation proposals from LLM output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from mutiny_core.genome.models import AttackMessage

MutationOperatorName = Literal[
    "semantic_rephrase",
    "authority_escalation",
    "multi_turn_setup",
    "confirmation_bypass",
    "argument_nudging",
    "indirect_request",
]


class MutationProposal(BaseModel):
    """Validated structured rewrite of attacker user messages."""

    operator: str
    messages: list[AttackMessage] = Field(..., min_length=1)

    @field_validator("messages")
    @classmethod
    def _non_empty_content(cls, messages: list[AttackMessage]) -> list[AttackMessage]:
        for m in messages:
            if not m.content.strip():
                raise ValueError("message content must be non-empty")
        return messages
