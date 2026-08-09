"""Typed campaign events for SSE bridging (payloads only — no I/O)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    CAMPAIGN_STARTED = "campaign.started"
    GENERATION_STARTED = "generation.started"
    CANDIDATE_CREATED = "candidate.created"
    CANDIDATE_EXECUTING = "candidate.executing"
    CANDIDATE_SCORED = "candidate.scored"
    VIOLATION_DETECTED = "violation.detected"
    MINIMIZATION_STARTED = "minimization.started"
    MINIMIZATION_STEP = "minimization.step"
    EXPLOIT_MINIMIZED = "exploit.minimized"
    REGRESSION_CREATED = "regression.created"
    CAMPAIGN_COMPLETED = "campaign.completed"
    CAMPAIGN_ERROR = "campaign.error"


class MutinyEvent(BaseModel):
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
