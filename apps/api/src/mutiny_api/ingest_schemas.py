"""Pydantic request models for Hosted observe-only ingestion (M-PR8B)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

INGEST_SCHEMA_VERSION = 1

# Observable event subset from HOSTED_INGESTION §5 (plus optional created).
INGEST_EVENT_TYPES = frozenset(
    {
        "campaign.started",
        "generation.started",
        "candidate.created",
        "candidate.scored",
        "violation.detected",
        "minimization.started",
        "exploit.minimized",
        "regression.created",
        "campaign.completed",
        "campaign.error",
    }
)

ARTIFACT_KINDS = frozenset(
    {"candidate", "trace", "minimize_result", "regression", "test_run"}
)


class RedactionAttestation(BaseModel):
    """CLI must attest secrets were redacted before upload.

    Hosted rejects applied=false / missing via service-layer checks so the
    machine code is ``redaction_required`` (400), not a generic 422.
    """

    applied: bool | None = None
    marker: str = "[REDACTED]"


class IngestEnvelopeBase(BaseModel):
    schema_version: int | None = Field(
        default=None, description="Ingestion contract version"
    )
    redaction: RedactionAttestation | None = None
    mutiny_version: str | None = None
    execution_mode: Literal["local_cli"] | str | None = "local_cli"


class IngestCampaignOpenRequest(IngestEnvelopeBase):
    """Open/upsert an observe-only campaign (client-supplied campaign_id)."""

    campaign_id: str = Field(..., min_length=1, max_length=128)
    project_id: str | None = None
    local_project_key: str | None = Field(default=None, max_length=512)
    project_name: str | None = Field(default=None, max_length=256)
    # Opaque display label only — never opened/stat'd/imported by Hosted ingest.
    project_label: str | None = Field(default=None, max_length=2048)
    adapter: str = "openai_agents"
    status: Literal["created", "running"] = "created"
    attestation: bool = True
    started_at: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    policy_id: str | None = None
    policy_version: str | None = None
    policy_hash: str | None = None


class IngestEventItem(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str | None = None
    candidate_id: str | None = None
    generation: int | None = None
    seq: int | None = Field(default=None, ge=0)


class IngestArtifactItem(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    id: str = Field(..., min_length=1, max_length=128)
    body: dict[str, Any] = Field(default_factory=dict)
    sha256: str | None = Field(default=None, max_length=128)
    campaign_id: str | None = None
    candidate_id: str | None = None
    # Opaque display path for regressions — never filesystem-accessed.
    path: str | None = Field(default=None, max_length=2048)


class IngestBatchRequest(IngestEnvelopeBase):
    campaign_id: str = Field(..., min_length=1, max_length=128)
    seq: int | None = Field(default=None, ge=0)
    events: list[IngestEventItem] = Field(default_factory=list)
    artifacts: list[IngestArtifactItem] = Field(default_factory=list)


class IngestCompleteRequest(IngestEnvelopeBase):
    status: Literal["completed", "failed", "violation"]
    metrics: dict[str, Any] | None = None
    completed_at: str | None = None
    reason: str | None = Field(default=None, max_length=1024)


class IngestRegressionRequest(IngestEnvelopeBase):
    regression_id: str = Field(..., min_length=1, max_length=128)
    campaign_id: str = Field(..., min_length=1, max_length=128)
    candidate_id: str | None = None
    # Opaque client display string — never opened by Hosted ingest.
    path: str | None = Field(default=None, max_length=2048)
    artifact: dict[str, Any] = Field(default_factory=dict)
    sha256: str | None = None


class IngestTestRunRequest(IngestEnvelopeBase):
    test_run_id: str = Field(..., min_length=1, max_length=128)
    regression_id: str = Field(..., min_length=1, max_length=128)
    status: Literal["PASS", "FAIL"]
    duration_ms: float | None = None
    policy_version: str | None = None
    agent_version: str | None = None
    fixed_agent: bool = False
    violated_rule_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    campaign_id: str | None = None
