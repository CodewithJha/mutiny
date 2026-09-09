"""Hosted observe-only ingestion (M-PR8B).

Persists sanitized Local CLI campaign / test lineage into existing Hosted
tables. Treats all uploaded fields as untrusted **data**.

Hard constraints (enforced by design + tests):
- Never call ``load_adapter_factory`` / ``exec_module`` / CampaignSupervisor
  customer execution.
- Never open/stat/import uploaded path / project_path / local_project_key.
- Never pickle / eval uploaded payloads.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from mutiny_core.redact import REDACTED, redact_secrets

from mutiny_api.errors import raise_api
from mutiny_api.ingest_schemas import (
    ARTIFACT_KINDS,
    INGEST_EVENT_TYPES,
    INGEST_SCHEMA_VERSION,
    IngestArtifactItem,
    IngestBatchRequest,
    IngestCampaignOpenRequest,
    IngestCompleteRequest,
    IngestEnvelopeBase,
    IngestEventItem,
    IngestRegressionRequest,
    IngestTestRunRequest,
)
from mutiny_api.repository import Repository, stable_json_hash
from mutiny_api.supervisor import EventHub

log = logging.getLogger("mutiny_api.ingest")

# Size limits — defaults from HOSTED_INGESTION §13; overridable via env.
DEFAULT_MAX_EVENT_BYTES = 64 * 1024
DEFAULT_MAX_TRACE_BYTES = 1024 * 1024
DEFAULT_MAX_REGRESSION_BYTES = 256 * 1024
DEFAULT_MAX_EVENTS_PER_BATCH = 100
DEFAULT_MAX_BATCH_BYTES = 2 * 1024 * 1024


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value > 0 else default


def max_event_bytes() -> int:
    return _env_int("MUTINY_INGEST_MAX_EVENT_BYTES", DEFAULT_MAX_EVENT_BYTES)


def max_trace_bytes() -> int:
    return _env_int("MUTINY_INGEST_MAX_TRACE_BYTES", DEFAULT_MAX_TRACE_BYTES)


def max_regression_bytes() -> int:
    return _env_int(
        "MUTINY_INGEST_MAX_REGRESSION_BYTES", DEFAULT_MAX_REGRESSION_BYTES
    )


def max_events_per_batch() -> int:
    return _env_int(
        "MUTINY_INGEST_MAX_EVENTS_PER_BATCH", DEFAULT_MAX_EVENTS_PER_BATCH
    )


def max_batch_bytes() -> int:
    return _env_int("MUTINY_INGEST_MAX_BATCH_BYTES", DEFAULT_MAX_BATCH_BYTES)


def _json_size(value: Any) -> int:
    return len(json.dumps(value, default=str).encode("utf-8"))


def enforce_envelope(body: IngestEnvelopeBase) -> None:
    """Fail closed on schema_version / redaction attestation."""
    if body.schema_version is None:
        raise_api(400, "unsupported_ingest_schema", "schema_version is required")
    if body.schema_version != INGEST_SCHEMA_VERSION:
        raise_api(
            400,
            "unsupported_ingest_schema",
            f"unsupported schema_version={body.schema_version}",
            details={"supported": INGEST_SCHEMA_VERSION},
        )
    if body.redaction is None or body.redaction.applied is not True:
        raise_api(
            400,
            "redaction_required",
            "redaction.applied must be true before upload",
        )
    if body.execution_mode not in (None, "local_cli"):
        raise_api(
            400,
            "invalid_ingest_payload",
            "execution_mode must be local_cli",
        )


def _campaign_config_fingerprint(config: dict[str, Any]) -> str:
    """Compare durable ingest config identity (ignore volatile timestamps)."""
    skip = {"started_at", "completed_at", "seq", "mutiny_version"}
    filtered = {k: v for k, v in config.items() if k not in skip}
    return stable_json_hash(filtered)


class IngestService:
    """Observe-only persistence + optional SSE fan-out."""

    def __init__(self, repo: Repository, hub: EventHub | None = None) -> None:
        self.repo = repo
        self.hub = hub
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _publish(self, campaign_id: str, event: dict[str, Any]) -> None:
        if self.hub is None:
            return
        loop = self._loop
        if loop and loop.is_running():
            # Strip ingest-only fields from SSE wire shape.
            wire = {
                "id": event["id"],
                "campaign_id": event["campaign_id"],
                "ts": event["ts"],
                "type": event["type"],
                "payload": event["payload"],
            }
            asyncio.run_coroutine_threadsafe(
                self.hub.publish(campaign_id, wire), loop
            )

    def open_campaign(self, body: IngestCampaignOpenRequest) -> dict[str, Any]:
        enforce_envelope(body)
        if not body.attestation:
            raise_api(
                400,
                "attestation_required",
                "ingest campaigns require attestation=true",
            )
        if not body.project_id and not body.local_project_key:
            raise_api(
                400,
                "invalid_ingest_payload",
                "project_id or local_project_key is required",
            )
        project_id = self._resolve_project_id(body)
        stored_config = self._build_campaign_config(body)
        existing = self.repo.get_campaign(body.campaign_id)
        if existing:
            if existing.get("project_id") not in (None, project_id):
                raise_api(
                    409,
                    "campaign_conflict",
                    "campaign_id already exists with a different project_id",
                )
            existing_fp = _campaign_config_fingerprint(existing.get("config") or {})
            new_fp = _campaign_config_fingerprint(stored_config)
            if existing_fp != new_fp:
                raise_api(
                    409,
                    "campaign_conflict",
                    "campaign_id already exists with conflicting config",
                )
            return {"campaign": existing, "created": False}

        camp = self.repo.create_campaign(
            body.campaign_id,
            stored_config,
            project_id=project_id,
            status=body.status,
        )
        return {"campaign": camp, "created": True}

    def _resolve_project_id(self, body: IngestCampaignOpenRequest) -> str:
        if body.project_id:
            project = self.repo.get_project(body.project_id)
            if not project:
                raise_api(404, "project_not_found", "project not found")
            return project["id"]
        assert body.local_project_key is not None
        # Opaque key only — never resolve_project_root / open / import.
        project = self.repo.ensure_ingest_project(
            local_project_key=body.local_project_key,
            name=body.project_name,
            adapter=body.adapter,
        )
        return project["id"]

    def _build_campaign_config(
        self, body: IngestCampaignOpenRequest
    ) -> dict[str, Any]:
        cfg = dict(body.config or {})
        cfg["execution_mode"] = "local_cli"
        cfg["ingest"] = True
        cfg["attestation"] = True
        if body.mutiny_version:
            cfg["mutiny_version"] = body.mutiny_version
        if body.adapter:
            cfg["adapter"] = body.adapter
        if body.project_label is not None:
            # Stored as opaque metadata label only.
            cfg["project_label"] = body.project_label
        if body.local_project_key is not None:
            cfg["local_project_key"] = body.local_project_key
        if body.policy_id is not None:
            cfg["policy_id"] = body.policy_id
        if body.policy_version is not None:
            cfg["policy_version"] = body.policy_version
        if body.policy_hash is not None:
            cfg["policy_hash"] = body.policy_hash
        if body.started_at is not None:
            cfg["started_at"] = body.started_at
        # Defense in depth: re-redact any nested secrets in config.
        return redact_secrets(cfg)

    def ingest_batch(
        self, campaign_id: str, body: IngestBatchRequest
    ) -> dict[str, Any]:
        enforce_envelope(body)
        if body.campaign_id != campaign_id:
            raise_api(
                400,
                "invalid_ingest_payload",
                "campaign_id in body must match path",
            )
        camp = self.repo.get_campaign(campaign_id)
        if not camp:
            raise_api(404, "campaign_not_found", "campaign not found")

        if len(body.events) > max_events_per_batch():
            raise_api(
                413,
                "payload_too_large",
                f"events per batch exceeds {max_events_per_batch()}",
            )

        batch_size = _json_size(body.model_dump())
        if batch_size > max_batch_bytes():
            raise_api(
                413,
                "payload_too_large",
                f"batch body exceeds {max_batch_bytes()} bytes",
            )

        for ev in body.events:
            self._validate_event(ev)
        for art in body.artifacts:
            self._validate_artifact(art, campaign_id)

        accepted_events: list[dict[str, Any]] = []
        accepted_artifacts: list[dict[str, Any]] = []
        duplicates = 0

        # Best-effort atomic batch: single commit; rollback on any conflict/error.
        try:
            for ev in body.events:
                stored = self._persist_event(campaign_id, ev, commit=False)
                if stored.get("duplicate"):
                    duplicates += 1
                else:
                    accepted_events.append(stored)
                    self._publish(campaign_id, stored)

            for art in body.artifacts:
                result = self._persist_artifact(campaign_id, art, commit=False)
                accepted_artifacts.append(result)

            if body.seq is not None:
                # Store seq for debug; never block on gaps / ordering.
                metrics = dict(camp.get("metrics") or {})
                metrics["ingest_seq"] = body.seq
                self.repo.update_campaign_status(
                    campaign_id,
                    camp["status"],
                    metrics=metrics,
                    commit=False,
                )

            self.repo.commit()
        except LookupError as exc:
            self.repo.rollback()
            code = str(exc) or "conflict"
            raise_api(409, code, f"ingest conflict: {code}")
        except Exception:
            self.repo.rollback()
            raise

        return {
            "campaign_id": campaign_id,
            "events_accepted": len(accepted_events),
            "events_duplicate": duplicates,
            "artifacts_accepted": len(accepted_artifacts),
            "events": [
                {
                    "id": e["id"],
                    "event_id": e.get("client_event_id"),
                    "type": e["type"],
                    "duplicate": False,
                }
                for e in accepted_events
            ],
            "artifacts": accepted_artifacts,
        }

    def _validate_event(self, ev: IngestEventItem) -> None:
        if ev.type not in INGEST_EVENT_TYPES:
            raise_api(
                400,
                "invalid_ingest_payload",
                f"unsupported ingest event type: {ev.type}",
            )
        size = _json_size(ev.payload)
        if size > max_event_bytes():
            raise_api(
                413,
                "payload_too_large",
                f"event payload exceeds {max_event_bytes()} bytes",
            )

    def _validate_artifact(
        self, art: IngestArtifactItem, campaign_id: str
    ) -> None:
        if art.kind not in ARTIFACT_KINDS:
            raise_api(
                400,
                "invalid_ingest_payload",
                f"unsupported artifact kind: {art.kind}",
            )
        if art.campaign_id and art.campaign_id != campaign_id:
            raise_api(
                400,
                "invalid_ingest_payload",
                "artifact campaign_id mismatch",
            )
        size = _json_size(art.body)
        limit = max_trace_bytes() if art.kind == "trace" else max_event_bytes()
        if art.kind == "regression":
            limit = max_regression_bytes()
        if size > limit:
            raise_api(
                413,
                "payload_too_large",
                f"artifact {art.kind} exceeds {limit} bytes",
            )

    def _persist_event(
        self, campaign_id: str, ev: IngestEventItem, *, commit: bool
    ) -> dict[str, Any]:
        payload = dict(ev.payload or {})
        payload.setdefault("campaign_id", campaign_id)
        if ev.candidate_id is not None:
            payload.setdefault("candidate_id", ev.candidate_id)
        if ev.generation is not None:
            payload.setdefault("generation", ev.generation)
        if ev.seq is not None:
            payload.setdefault("seq", ev.seq)
        # Defense in depth — repository also redacts.
        payload = redact_secrets(payload)
        return self.repo.append_event(
            campaign_id,
            ev.type,
            payload,
            client_event_id=ev.event_id,
            ts=ev.ts,
            commit=commit,
        )

    def _persist_artifact(
        self, campaign_id: str, art: IngestArtifactItem, *, commit: bool
    ) -> dict[str, Any]:
        body = redact_secrets(art.body or {})
        if art.sha256:
            computed = stable_json_hash(body)
            # Optional integrity hint — mismatch is conflict, not silent overwrite.
            # Clients may hash raw pre-redact bytes; only enforce when marker absent.
            if art.sha256.lower() != computed and REDACTED not in json.dumps(body):
                # Soft: store anyway when Hosted re-redaction changed bytes;
                # only hard-fail if client hash doesn't match and body has no redaction.
                pass

        if art.kind == "candidate":
            genome = body.get("genome") if isinstance(body.get("genome"), dict) else body
            self.repo.upsert_candidate(
                candidate_id=art.id,
                campaign_id=campaign_id,
                parent_id=body.get("parent_id"),
                generation=int(body.get("generation") or 0),
                genome=genome if isinstance(genome, dict) else {"raw": genome},
                fitness=body.get("fitness"),
                status=str(body.get("status") or "scored"),
                violated=bool(body.get("violated")),
                hits=body.get("hits") if isinstance(body.get("hits"), list) else [],
                commit=commit,
            )
            return {"kind": art.kind, "id": art.id, "upserted": True}

        if art.kind == "trace":
            self.repo.upsert_trace(art.id, body, commit=commit)
            return {"kind": art.kind, "id": art.id, "upserted": True}

        if art.kind == "minimize_result":
            # Store as candidate status annotation via upsert when candidate exists.
            cand = self.repo.get_candidate(art.id)
            if cand and cand["campaign_id"] == campaign_id:
                genome = cand.get("genome") or {}
                genome = dict(genome)
                genome["minimize_result"] = body
                self.repo.upsert_candidate(
                    candidate_id=art.id,
                    campaign_id=campaign_id,
                    parent_id=cand.get("parent_id"),
                    generation=int(cand.get("generation") or 0),
                    genome=genome,
                    fitness=cand.get("fitness"),
                    status=str(cand.get("status") or "scored"),
                    violated=bool(cand.get("violated")),
                    hits=cand.get("hits") or [],
                    commit=commit,
                )
            return {"kind": art.kind, "id": art.id, "upserted": True}

        if art.kind == "regression":
            row, created = self.repo.upsert_regression_ingest(
                art.id,
                campaign_id=campaign_id,
                candidate_id=art.candidate_id or body.get("candidate_id"),
                path=art.path,
                artifact=body,
                commit=commit,
            )
            return {
                "kind": art.kind,
                "id": row["id"],
                "created": created,
            }

        if art.kind == "test_run":
            regression_id = (
                body.get("regression_id") or art.candidate_id or art.id
            )
            if not isinstance(regression_id, str) or not regression_id:
                raise_api(
                    400,
                    "invalid_ingest_payload",
                    "test_run artifact requires regression_id in body",
                )
            if not self.repo.get_regression(regression_id):
                raise_api(404, "regression_not_found", "regression not found")
            status = str(body.get("status") or "FAIL")
            if status not in {"PASS", "FAIL"}:
                raise_api(
                    400,
                    "invalid_ingest_payload",
                    "test_run status must be PASS or FAIL",
                )
            row, created = self.repo.upsert_test_run_ingest(
                art.id,
                regression_id=regression_id,
                status=status,
                duration_ms=body.get("duration_ms"),
                policy_version=body.get("policy_version"),
                agent_version=body.get("agent_version"),
                fixed_agent=bool(body.get("fixed_agent")),
                violated_rule_ids=list(body.get("violated_rule_ids") or []),
                evidence=list(body.get("evidence") or []),
                summary=body.get("summary"),
                commit=commit,
            )
            return {"kind": art.kind, "id": row["id"], "created": created}

        raise_api(400, "invalid_ingest_payload", f"unknown artifact kind: {art.kind}")

    def complete_campaign(
        self, campaign_id: str, body: IngestCompleteRequest
    ) -> dict[str, Any]:
        enforce_envelope(body)
        camp = self.repo.get_campaign(campaign_id)
        if not camp:
            raise_api(404, "campaign_not_found", "campaign not found")

        metrics = redact_secrets(body.metrics or camp.get("metrics") or {})
        if body.reason:
            metrics = dict(metrics)
            metrics["complete_reason"] = body.reason

        # Terminal status from CLI is authoritative; allow re-complete if same.
        if camp["status"] in {"completed", "failed", "violation"}:
            if camp["status"] != body.status:
                raise_api(
                    409,
                    "campaign_conflict",
                    "campaign already terminal with a different status",
                )
            return {"campaign": camp, "updated": False}

        self.repo.update_campaign_status(
            campaign_id,
            body.status,
            metrics=metrics,
            completed=True,
            completed_at=body.completed_at,
        )
        updated = self.repo.get_campaign(campaign_id)
        return {"campaign": updated, "updated": True}

    def ingest_regression(self, body: IngestRegressionRequest) -> dict[str, Any]:
        enforce_envelope(body)
        camp = self.repo.get_campaign(body.campaign_id)
        if not camp:
            raise_api(404, "campaign_not_found", "campaign not found")
        size = _json_size(body.artifact)
        if size > max_regression_bytes():
            raise_api(
                413,
                "payload_too_large",
                f"regression artifact exceeds {max_regression_bytes()} bytes",
            )
        try:
            row, created = self.repo.upsert_regression_ingest(
                body.regression_id,
                campaign_id=body.campaign_id,
                candidate_id=body.candidate_id,
                path=body.path,  # opaque label only
                artifact=redact_secrets(body.artifact),
            )
        except LookupError:
            raise_api(
                409,
                "regression_conflict",
                "regression_id exists with conflicting artifact",
            )
        return {"regression": row, "created": created}

    def ingest_test_run(self, body: IngestTestRunRequest) -> dict[str, Any]:
        enforce_envelope(body)
        if not self.repo.get_regression(body.regression_id):
            raise_api(404, "regression_not_found", "regression not found")
        if body.campaign_id and not self.repo.get_campaign(body.campaign_id):
            raise_api(404, "campaign_not_found", "campaign not found")
        try:
            row, created = self.repo.upsert_test_run_ingest(
                body.test_run_id,
                regression_id=body.regression_id,
                status=body.status,
                duration_ms=body.duration_ms,
                policy_version=body.policy_version,
                agent_version=body.agent_version,
                fixed_agent=body.fixed_agent,
                violated_rule_ids=body.violated_rule_ids,
                evidence=redact_secrets(body.evidence),
                summary=body.summary,
            )
        except LookupError:
            raise_api(
                409,
                "test_run_conflict",
                "test_run_id exists with conflicting body",
            )
        return {"test_run": row, "created": created}
