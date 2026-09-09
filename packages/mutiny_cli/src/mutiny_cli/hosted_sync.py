"""CLI → Hosted observe-only sync (M-PR8C).

End-of-run synchronization: Local Core executes the campaign; this module
builds redacted ``schema_version=1`` ingest envelopes and POSTs them to
``/api/ingest/v1/*``. No Hosted customer ``exec_module`` / CampaignSupervisor.

HTTP stays in the CLI package — never in ``mutiny_core``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

from mutiny_core import __version__ as MUTINY_VERSION
from mutiny_core.campaign.engine import CampaignResult, ScoredCandidate
from mutiny_core.events import EventType, MutinyEvent
from mutiny_core.redact import REDACTED, redact_secrets, redaction_enabled

log = logging.getLogger("mutiny_cli.hosted_sync")

INGEST_SCHEMA_VERSION = 1
EXECUTION_MODE = "local_cli"
DEFAULT_TIMEOUT_S = 30.0

# Local campaign OK but Hosted sync failed / refused (distinct from local fail=1).
SYNC_FAILED_EXIT = 3

# Observable subset (HOSTED_INGESTION §5) — drop high-noise Core events.
_UPLOAD_EVENT_TYPES = frozenset(
    {
        EventType.CAMPAIGN_STARTED.value,
        EventType.GENERATION_STARTED.value,
        EventType.CANDIDATE_SCORED.value,
        EventType.VIOLATION_DETECTED.value,
        EventType.MINIMIZATION_STARTED.value,
        EventType.EXPLOIT_MINIMIZED.value,
        EventType.REGRESSION_CREATED.value,
        EventType.CAMPAIGN_COMPLETED.value,
        EventType.CAMPAIGN_ERROR.value,
    }
)

_SKIP_SCORED_KEYS = frozenset({"trace", "genome"})


@dataclass
class SyncOutcome:
    """Result of a Hosted ingest attempt (orthogonal to local exit code)."""

    ok: bool
    message: str = ""
    error_code: str | None = None
    http_status: int | None = None
    pending_path: Path | None = None


@dataclass
class LocalRunBundle:
    """Sanitized local campaign outcome ready for Hosted ingest."""

    campaign_id: str
    project_root: Path
    config: dict[str, Any]
    policy_version: str | None
    policy_target: str | None
    result: CampaignResult
    events: list[MutinyEvent] = field(default_factory=list)
    regression_id: str | None = None
    regression_path: str | None = None
    regression_artifact: dict[str, Any] | None = None
    minimize_body: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None


def auth_headers_from_env() -> dict[str, str]:
    """Bearer headers from ``MUTINY_API_TOKEN`` when set (never log the value)."""
    raw = os.environ.get("MUTINY_API_TOKEN")
    if raw is None:
        return {}
    token = raw.strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def local_project_key(project_root: Path, *, adapter: str = "openai_agents") -> str:
    """Opaque project identity — hash of resolved root + adapter (not a FS mount)."""
    material = f"{project_root.resolve()}|{adapter}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"cli:{digest}"


def redaction_envelope() -> dict[str, Any]:
    return {"applied": True, "marker": REDACTED}


def ensure_redaction_allowed_for_upload() -> None:
    """Refuse Hosted upload when M-PR3 redaction is disabled."""
    if not redaction_enabled():
        raise RedactionDisabledError(
            "Hosted sync refused: MUTINY_DISABLE_SECRET_REDACTION disables "
            "secret redaction; uploads require redaction.applied=true"
        )


class RedactionDisabledError(RuntimeError):
    """Raised when Hosted upload is refused because redaction is off."""


class HostedSyncError(RuntimeError):
    """Hosted ingest HTTP / protocol failure."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _event_id(campaign_id: str, seq: int, event_type: str) -> str:
    """Stable client event IDs for idempotent retry of the same local run."""
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"mutiny:ingest:{campaign_id}:{seq}:{event_type}",
        )
    )


def _strip_trace_raw(trace: dict[str, Any]) -> dict[str, Any]:
    """Drop verbose ``raw`` blobs from turns before upload size limits."""
    turns = trace.get("turns")
    if not isinstance(turns, list):
        return trace
    cleaned_turns = []
    for turn in turns:
        if not isinstance(turn, dict):
            cleaned_turns.append(turn)
            continue
        t = dict(turn)
        t.pop("raw", None)
        cleaned_turns.append(t)
    out = dict(trace)
    out["turns"] = cleaned_turns
    return out


def _candidate_summary(scored: ScoredCandidate) -> dict[str, Any]:
    genome = scored.genome
    return {
        "id": genome.id,
        "generation": genome.generation,
        "fitness": scored.fitness,
        "violated": scored.violated,
        "status": "violator" if scored.violated else "scored",
        "parent_id": genome.parent_id,
        "strategy": genome.strategy,
        "mutations": list(genome.mutations),
        "target_rule_ids": list(genome.target_rule_ids),
        "policy_hits": [
            {
                "rule_id": h.rule_id,
                "violated": h.violated,
                "tool": getattr(getattr(h, "evidence", None), "tool_name", None),
            }
            for h in scored.hits
        ],
        "signals": dict(scored.signals),
        "message_count": len(genome.messages),
    }


def _scored_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Summary-only candidate.scored payload (no full trace/genome in events)."""
    out = {k: v for k, v in payload.items() if k not in _SKIP_SCORED_KEYS}
    return out


def build_ingest_events(
    campaign_id: str, events: list[MutinyEvent]
) -> list[dict[str, Any]]:
    """Map Core events → ingest event items with stable IDs."""
    items: list[dict[str, Any]] = []
    seq = 0
    for ev in events:
        etype = ev.type.value if isinstance(ev.type, EventType) else str(ev.type)
        if etype not in _UPLOAD_EVENT_TYPES:
            continue
        seq += 1
        payload = dict(ev.payload or {})
        if etype == EventType.CANDIDATE_SCORED.value:
            payload = _scored_event_payload(payload)
        payload.setdefault("campaign_id", campaign_id)
        candidate_id = payload.get("candidate_id")
        generation = payload.get("generation")
        items.append(
            {
                "event_id": _event_id(campaign_id, seq, etype),
                "type": etype,
                "payload": redact_secrets(payload),
                "candidate_id": str(candidate_id) if candidate_id else None,
                "generation": int(generation) if generation is not None else None,
                "seq": seq,
            }
        )
    return items


def build_artifacts(bundle: LocalRunBundle) -> list[dict[str, Any]]:
    """Candidate / trace / minimize / regression artifacts (redacted)."""
    arts: list[dict[str, Any]] = []
    # Prefer best + violators; cap volume for size limits.
    scored = list(bundle.result.candidates)
    preferred: list[ScoredCandidate] = []
    if bundle.result.best is not None:
        preferred.append(bundle.result.best)
    for c in scored:
        if c.violated and (
            bundle.result.best is None or c.genome.id != bundle.result.best.genome.id
        ):
            preferred.append(c)
    # Include a few non-violators for lineage (first generation samples).
    for c in scored:
        if len(preferred) >= 8:
            break
        if all(p.genome.id != c.genome.id for p in preferred):
            preferred.append(c)

    for c in preferred:
        cid = c.genome.id
        body = redact_secrets(_candidate_summary(c))
        arts.append(
            {
                "kind": "candidate",
                "id": cid,
                "candidate_id": cid,
                "campaign_id": bundle.campaign_id,
                "body": body,
            }
        )
        trace_body = redact_secrets(
            _strip_trace_raw(c.trace.model_dump(mode="json"))
        )
        arts.append(
            {
                "kind": "trace",
                "id": cid,
                "candidate_id": cid,
                "campaign_id": bundle.campaign_id,
                "body": trace_body,
            }
        )

    if bundle.minimize_body is not None and bundle.result.best is not None:
        mid = bundle.result.best.genome.id
        arts.append(
            {
                "kind": "minimize_result",
                "id": mid,
                "candidate_id": mid,
                "campaign_id": bundle.campaign_id,
                "body": redact_secrets(bundle.minimize_body),
            }
        )

    if bundle.regression_artifact is not None and bundle.regression_id:
        arts.append(
            {
                "kind": "regression",
                "id": bundle.regression_id,
                "candidate_id": (bundle.regression_artifact.get("provenance") or {}).get(
                    "candidate_id"
                ),
                "campaign_id": bundle.campaign_id,
                "path": bundle.regression_path,
                "body": redact_secrets(bundle.regression_artifact),
            }
        )
    return arts


def terminal_status(result: CampaignResult) -> Literal["completed", "failed", "violation"]:
    if result.status == "violation" or result.violated:
        return "violation"
    if result.status == "error":
        return "failed"
    return "completed"


def build_campaign_open_payload(bundle: LocalRunBundle) -> dict[str, Any]:
    ensure_redaction_allowed_for_upload()
    adapter = "openai_agents"
    cfg = {
        "population_size": int(bundle.config.get("population_size", 8)),
        "max_generations": int(bundle.config.get("max_generations", 6)),
        "elite_count": int(bundle.config.get("elite_count", 2)),
        "max_turns": int(bundle.config.get("max_turns", 4)),
        "stop_on_first_violation": bool(
            bundle.config.get("stop_on_first_violation", True)
        ),
        "rng_seed": int(bundle.config.get("rng_seed", 0)),
        "use_boundary_seeds": bool(bundle.config.get("use_boundary_seeds", True)),
        "execution_mode": EXECUTION_MODE,
        "adapter": adapter,
    }
    return {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": MUTINY_VERSION,
        "execution_mode": EXECUTION_MODE,
        "redaction": redaction_envelope(),
        "campaign_id": bundle.campaign_id,
        "local_project_key": local_project_key(bundle.project_root, adapter=adapter),
        "project_name": bundle.project_root.name,
        "project_label": bundle.project_root.name,
        "adapter": adapter,
        "status": "running",
        "attestation": True,
        "started_at": bundle.started_at or _utcnow(),
        "config": cfg,
        "policy_version": bundle.policy_version,
        "policy_id": bundle.policy_target,
    }


def build_batch_payload(bundle: LocalRunBundle, *, seq: int = 1) -> dict[str, Any]:
    ensure_redaction_allowed_for_upload()
    return {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": MUTINY_VERSION,
        "execution_mode": EXECUTION_MODE,
        "redaction": redaction_envelope(),
        "campaign_id": bundle.campaign_id,
        "seq": seq,
        "events": build_ingest_events(bundle.campaign_id, bundle.events),
        "artifacts": build_artifacts(bundle),
    }


def build_complete_payload(bundle: LocalRunBundle) -> dict[str, Any]:
    ensure_redaction_allowed_for_upload()
    status = terminal_status(bundle.result)
    metrics = {
        "candidates": len(bundle.result.candidates),
        "generations": bundle.result.generations_completed,
        "violated": bundle.result.violated,
        "events_emitted": bundle.result.events_emitted,
        "reason": bundle.result.reason,
    }
    return {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": MUTINY_VERSION,
        "execution_mode": EXECUTION_MODE,
        "redaction": redaction_envelope(),
        "status": status,
        "metrics": metrics,
        "completed_at": bundle.completed_at or _utcnow(),
        "reason": bundle.result.reason,
    }


def build_regression_payload(bundle: LocalRunBundle) -> dict[str, Any] | None:
    if not bundle.regression_id or bundle.regression_artifact is None:
        return None
    ensure_redaction_allowed_for_upload()
    artifact = redact_secrets(bundle.regression_artifact)
    cand = (artifact.get("provenance") or {}).get("candidate_id")
    return {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": MUTINY_VERSION,
        "execution_mode": EXECUTION_MODE,
        "redaction": redaction_envelope(),
        "regression_id": bundle.regression_id,
        "campaign_id": bundle.campaign_id,
        "candidate_id": cand,
        "path": bundle.regression_path,
        "artifact": artifact,
    }


def build_test_run_payload(
    *,
    test_run_id: str,
    regression_id: str,
    status: Literal["PASS", "FAIL"],
    duration_ms: float | None = None,
    policy_version: str | None = None,
    violated_rule_ids: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    summary: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    """Build a test-run ingest envelope (for future ``mutiny test --hosted``)."""
    ensure_redaction_allowed_for_upload()
    return {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": MUTINY_VERSION,
        "execution_mode": EXECUTION_MODE,
        "redaction": redaction_envelope(),
        "test_run_id": test_run_id,
        "regression_id": regression_id,
        "status": status,
        "duration_ms": duration_ms,
        "policy_version": policy_version,
        "violated_rule_ids": list(violated_rule_ids or []),
        "evidence": redact_secrets(list(evidence or [])),
        "summary": summary,
        "campaign_id": campaign_id,
    }


def pending_dir(project_root: Path) -> Path:
    return project_root / ".mutiny" / "hosted-pending"


def write_pending_bundle(bundle: LocalRunBundle, payloads: dict[str, Any]) -> Path:
    """Write sanitized sync artifact for a future retry (not auto-executed)."""
    out_dir = pending_dir(bundle.project_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{bundle.campaign_id}.json"
    doc = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "kind": "hosted_pending_sync",
        "campaign_id": bundle.campaign_id,
        "created_at": _utcnow(),
        "note": "Sanitized ingest payloads; not executable. Retry is future work.",
        "payloads": payloads,
    }
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


class HostedIngestClient:
    """Thin httpx client for ``/api/ingest/v1/*`` (timeouts; no token logging)."""

    def __init__(
        self,
        api_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.headers = dict(headers or {})

    def _url(self, path: str) -> str:
        return urljoin(self.api_url + "/", path.lstrip("/"))

    def _client(self) -> Any:
        import httpx

        return httpx.Client(
            base_url=self.api_url,
            timeout=self.timeout,
            headers=self.headers,
        )

    def _raise_for_response(self, response: Any, *, action: str) -> None:
        if response.status_code < 400:
            return
        code = None
        detail = ""
        try:
            body = response.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                code = err.get("code")
                detail = str(err.get("message") or "")
        except Exception:  # noqa: BLE001
            detail = (getattr(response, "text", None) or "")[:200]
        status = int(response.status_code)
        if status == 401:
            msg = "Hosted authentication failed (set a valid MUTINY_API_TOKEN)"
            code = code or "unauthorized"
        elif status == 409:
            msg = f"Hosted identity conflict during {action}"
            code = code or "conflict"
        elif status == 413:
            msg = f"Hosted rejected oversized payload during {action}"
            code = code or "payload_too_large"
        elif code == "redaction_required":
            msg = "Hosted rejected upload: redaction.applied required"
        elif code == "unsupported_ingest_schema":
            msg = "Hosted rejected upload: unsupported ingest schema"
        else:
            msg = f"Hosted {action} failed (HTTP {status})"
            if detail:
                msg = f"{msg}: {detail[:160]}"
        raise HostedSyncError(msg, error_code=code, http_status=status)

    def open_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            r = client.post("/api/ingest/v1/campaigns", json=payload)
            self._raise_for_response(r, action="campaign open")
            return r.json()

    def post_batch(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            r = client.post(
                f"/api/ingest/v1/campaigns/{campaign_id}/batch", json=payload
            )
            self._raise_for_response(r, action="batch ingest")
            return r.json()

    def complete_campaign(
        self, campaign_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self._client() as client:
            r = client.post(
                f"/api/ingest/v1/campaigns/{campaign_id}/complete", json=payload
            )
            self._raise_for_response(r, action="campaign complete")
            return r.json()

    def post_regression(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            r = client.post("/api/ingest/v1/regressions", json=payload)
            self._raise_for_response(r, action="regression ingest")
            return r.json()

    def post_test_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            r = client.post("/api/ingest/v1/test-runs", json=payload)
            self._raise_for_response(r, action="test-run ingest")
            return r.json()


def sync_local_campaign(
    bundle: LocalRunBundle,
    *,
    api_url: str,
    ui_url: str | None = None,
    client: HostedIngestClient | None = None,
    write_pending_on_failure: bool = True,
) -> SyncOutcome:
    """Upload a finished local campaign via end-of-run ingest (open→batch→complete)."""
    try:
        ensure_redaction_allowed_for_upload()
    except RedactionDisabledError as exc:
        return SyncOutcome(ok=False, message=str(exc), error_code="redaction_disabled")

    open_body = build_campaign_open_payload(bundle)
    batch_body = build_batch_payload(bundle, seq=1)
    complete_body = build_complete_payload(bundle)
    regression_body = build_regression_payload(bundle)
    payloads = {
        "open": open_body,
        "batch": batch_body,
        "complete": complete_body,
        "regression": regression_body,
    }

    ingest = client or HostedIngestClient(
        api_url, headers=auth_headers_from_env()
    )
    try:
        ingest.open_campaign(open_body)
        ingest.post_batch(bundle.campaign_id, batch_body)
        if regression_body is not None:
            ingest.post_regression(regression_body)
        ingest.complete_campaign(bundle.campaign_id, complete_body)
    except HostedSyncError as exc:
        pending = None
        if write_pending_on_failure:
            try:
                pending = write_pending_bundle(bundle, payloads)
            except OSError as ose:  # noqa: BLE001
                log.debug("could not write hosted-pending: %s", ose)
        return SyncOutcome(
            ok=False,
            message=str(exc),
            error_code=exc.error_code,
            http_status=exc.http_status,
            pending_path=pending,
        )
    except Exception as exc:  # noqa: BLE001
        pending = None
        if write_pending_on_failure:
            try:
                pending = write_pending_bundle(bundle, payloads)
            except OSError as ose:  # noqa: BLE001
                log.debug("could not write hosted-pending: %s", ose)
        return SyncOutcome(
            ok=False,
            message=f"Hosted unreachable ({exc})",
            error_code="hosted_unavailable",
            pending_path=pending,
        )

    dash = None
    if ui_url:
        dash = f"{ui_url.rstrip('/')}/campaign/{bundle.campaign_id}"
    msg = f"Hosted sync ok · campaign {bundle.campaign_id}"
    if dash:
        msg = f"{msg}\n  dashboard   {dash}"
    return SyncOutcome(ok=True, message=msg)
