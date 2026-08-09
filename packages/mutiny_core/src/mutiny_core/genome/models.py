"""AttackGenome — SYSTEM_DESIGN §3 / §22."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AttackMessage(BaseModel):
    """Single attacker turn. Role is user-only for genomes."""

    role: Literal["user"] = "user"
    content: str = Field(..., min_length=1, max_length=4000)


class AttackGenome(BaseModel):
    """Candidate attack conversation (user messages only)."""

    id: str
    parent_id: str | None = None
    generation: int = Field(default=0, ge=0)
    strategy: str = "seed"
    mutations: list[str] = Field(default_factory=list)
    target_rule_ids: list[str] = Field(default_factory=list)
    messages: list[AttackMessage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
