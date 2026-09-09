"""M-PR8C integration: CLI-built ingest payloads against Hosted ingest API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_cli.hosted_sync import (
    LocalRunBundle,
    build_batch_payload,
    build_campaign_open_payload,
    build_complete_payload,
)
from mutiny_core.campaign.engine import CampaignResult, ScoredCandidate
from mutiny_core.events import EventType, MutinyEvent
from mutiny_core.genome.models import AttackGenome, AttackMessage
from mutiny_core.trace.models import ExecutionTrace


FAKE_TOKEN = "test-mpr8c-ingest-integration-token"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "cli_sync.sqlite"


@pytest.fixture
def client(api_db: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MUTINY_API_TOKEN", FAKE_TOKEN)
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {FAKE_TOKEN}"}


def _bundle(tmp: Path) -> LocalRunBundle:
    genome = AttackGenome(
        id="cand-int-1",
        messages=[AttackMessage(content="hello")],
    )
    scored = ScoredCandidate(
        genome=genome,
        trace=ExecutionTrace(
            candidate_id="cand-int-1",
            session_id="s1",
            status="scored",
        ),
        fitness=0.2,
        violated=False,
    )
    result = CampaignResult(
        status="completed",
        reason="gmax",
        generations_completed=1,
        candidates=[scored],
        best=scored,
        violated=False,
        events_emitted=2,
    )
    return LocalRunBundle(
        campaign_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        project_root=tmp,
        config={"population_size": 2, "max_generations": 1, "rng_seed": 0},
        policy_version="1",
        policy_target="openai_agents_project",
        result=result,
        events=[
            MutinyEvent(type=EventType.CAMPAIGN_STARTED, payload={"population_size": 2}),
            MutinyEvent(
                type=EventType.CAMPAIGN_COMPLETED,
                payload={"reason": "gmax", "generations": 1},
            ),
        ],
        started_at="2026-09-09T00:00:00Z",
        completed_at="2026-09-09T00:00:02Z",
    )


def test_cli_built_payloads_ingest_end_to_end(client: TestClient, tmp_path: Path) -> None:
    """CLI payload builders must be accepted by M-PR8B ingest routes."""
    bundle = _bundle(tmp_path)
    open_body = build_campaign_open_payload(bundle)
    batch_body = build_batch_payload(bundle)
    complete_body = build_complete_payload(bundle)

    assert open_body["execution_mode"] == "local_cli"
    assert "project_path" not in open_body

    r1 = client.post("/api/ingest/v1/campaigns", headers=_auth(), json=open_body)
    assert r1.status_code in (200, 201), r1.text

    r2 = client.post(
        f"/api/ingest/v1/campaigns/{bundle.campaign_id}/batch",
        headers=_auth(),
        json=batch_body,
    )
    assert r2.status_code == 200, r2.text

    r3 = client.post(
        f"/api/ingest/v1/campaigns/{bundle.campaign_id}/complete",
        headers=_auth(),
        json=complete_body,
    )
    assert r3.status_code == 200, r3.text

    camp = client.get(f"/api/campaigns/{bundle.campaign_id}", headers=_auth())
    assert camp.status_code == 200
    assert camp.json()["status"] == "completed"
    assert camp.json()["id"] == bundle.campaign_id

    cands = client.get(
        f"/api/campaigns/{bundle.campaign_id}/candidates", headers=_auth()
    )
    assert cands.status_code == 200
    assert any(c["id"] == "cand-int-1" for c in cands.json().get("candidates") or [])

    # Idempotent retry with identical CLI payloads.
    assert (
        client.post("/api/ingest/v1/campaigns", headers=_auth(), json=open_body).status_code
        in (200, 201)
    )
    assert (
        client.post(
            f"/api/ingest/v1/campaigns/{bundle.campaign_id}/batch",
            headers=_auth(),
            json=batch_body,
        ).status_code
        == 200
    )
