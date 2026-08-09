"""M6 Hosted API integration tests."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "test_mutiny.sqlite"


@pytest.fixture
def client(api_db: Path):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _wait_campaign(client: TestClient, campaign_id: str, timeout: float = 30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/campaigns/{campaign_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] not in {"created", "running"}:
            return body
        time.sleep(0.05)
    raise AssertionError("campaign did not finish in time")


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] is True
    assert body["db"] is True
    assert body["status"] == "ok"
    assert "openai_agents" in body["target_allowlist"]
    assert "in_process_demo" in body["target_allowlist"]
    assert body["adapter_loading"] == "project_path"
    assert "openai_support_agent" not in body["target_allowlist"]


def test_meta_project_path_model(client: TestClient):
    r = client.get("/api/meta")
    assert r.status_code == 200
    safety = r.json()["safety"]
    assert "openai_agents" in safety["targets"]
    assert "openai_agents" in safety["project_path_required_for"]


def test_policies_load_from_project(client: TestClient):
    r = client.get(
        "/api/policies",
        params={"project_path": "examples/openai_support_agent"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["policies"][0]["id"] == "openai_support_agent"
    assert body["policies"][0]["version"] == "1"
    assert "refund_limit" in json.dumps(body)
    assert any(
        "explanation" in rule
        for rule in body["policies"][0]["policy_set"]["rules"]
    )

    r2 = client.get(
        "/api/policies/openai_support_agent",
        params={"project_path": "examples/openai_support_agent"},
    )
    assert r2.status_code == 200
    assert "refund_limit" in json.dumps(r2.json())

    # Default project_path = sample (local Hosted UX)
    r3 = client.get("/api/policies")
    assert r3.status_code == 200
    assert r3.json()["policies"][0]["id"] == "openai_support_agent"


def test_policy_content_get_put_reload(client: TestClient, tmp_path: Path):
    """View / Edit / Save / Reload against a temp project copy."""
    import shutil

    sample = Path(__file__).resolve().parents[2] / "examples" / "openai_support_agent"
    project = tmp_path / "cust"
    shutil.copytree(sample, project)

    got = client.get("/api/policies/content", params={"project_path": str(project)})
    assert got.status_code == 200
    content = got.json()["content"]
    assert "refund_limit" in content
    assert got.json()["version"] == "1"

    # Invalid save rejected
    bad = client.put(
        "/api/policies/content",
        params={"project_path": str(project)},
        json={"content": "version: '1'\ntarget: t\nrules: oops\n"},
    )
    assert bad.status_code == 400

    # Bump version and save
    updated = content.replace('version: "1"', 'version: "2"', 1)
    if updated == content:
        updated = content.replace("version: '1'", "version: '2'", 1)
    saved = client.put(
        "/api/policies/content",
        params={"project_path": str(project)},
        json={"content": updated},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == "2"
    assert saved.json()["ok"] is True

    again = client.get("/api/policies/content", params={"project_path": str(project)})
    assert again.json()["version"] == "2"


def test_attestation_required(client: TestClient):
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 2,
            "rng_seed": 1,
            "use_boundary_seeds": True,
        },
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    denied = client.post(
        f"/api/campaigns/{cid}/start", json={"attestation": False}
    )
    assert denied.status_code == 403


def test_full_campaign_minimize_regression_flow(client: TestClient):
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 8,
            "max_generations": 3,
            "elite_count": 2,
            "stop_on_first_violation": True,
            "max_turns": 3,
            "rng_seed": 5,
            "use_boundary_seeds": True,
            "target": "in_process_demo",
        },
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert created.json()["status"] == "created"

    started = client.post(
        f"/api/campaigns/{cid}/start", json={"attestation": True}
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    final = _wait_campaign(client, cid)
    assert final["status"] in {"violation", "completed"}
    assert final["status"] == "violation" or final.get("metrics", {}).get("violated")

    cands = client.get(f"/api/campaigns/{cid}/candidates")
    assert cands.status_code == 200
    candidates = cands.json()["candidates"]
    assert len(candidates) >= 1
    assert all("genome" in c for c in candidates)

    violators = [c for c in candidates if c.get("violated")]
    assert violators, "expected at least one persisted violator"
    vid = violators[0]["id"]

    detail = client.get(f"/api/candidates/{vid}")
    assert detail.status_code == 200
    assert detail.json()["trace"] is not None
    assert detail.json()["genome"]["messages"]

    with client.stream("GET", f"/api/campaigns/{cid}/events") as resp:
        assert resp.status_code == 200
        blob = ""
        for chunk in resp.iter_text():
            blob += chunk
            if (
                "candidate.scored" in blob
                or "violation.detected" in blob
                or "campaign.completed" in blob
            ):
                break
            if len(blob) > 100_000:
                break
    assert (
        "candidate.scored" in blob
        or "violation.detected" in blob
        or "ready" in blob
        or "campaign.started" in blob
    )

    minimized = client.post(f"/api/candidates/{vid}/minimize", json={})
    assert minimized.status_code == 200
    assert minimized.json()["still_reproduces"] is True
    assert minimized.json()["minimized_turn_count"] >= 1

    reg = client.post(
        f"/api/candidates/{vid}/regression",
        json={"name": "api_refund_limit"},
    )
    assert reg.status_code == 201
    rid = reg.json()["id"]
    assert reg.json()["artifact"]["expected"]["must_not_violate"] == ["refund_limit"]

    fail = client.post(
        "/api/tests/run", json={"regression_id": rid, "fixed_agent": False}
    )
    assert fail.status_code == 200
    assert fail.json()["status"] == "FAIL"

    passed = client.post(
        "/api/tests/run", json={"regression_id": rid, "fixed_agent": True}
    )
    assert passed.status_code == 200
    assert passed.json()["status"] == "PASS"


def test_concurrency_guard(client: TestClient):
    a = client.post(
        "/api/campaigns",
        json={
            "population_size": 8,
            "max_generations": 6,
            "rng_seed": 0,
            "use_boundary_seeds": True,
            "stop_on_first_violation": False,
        },
    )
    b = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 2,
            "rng_seed": 1,
            "use_boundary_seeds": True,
        },
    )
    aid, bid = a.json()["id"], b.json()["id"]
    start_a = client.post(f"/api/campaigns/{aid}/start", json={"attestation": True})
    assert start_a.status_code == 200
    start_b = client.post(f"/api/campaigns/{bid}/start", json={"attestation": True})
    assert start_b.status_code == 409
    _wait_campaign(client, aid, timeout=60.0)


def test_events_table_has_scored_events(client: TestClient, api_db: Path):
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 8,
            "max_generations": 2,
            "rng_seed": 3,
            "use_boundary_seeds": True,
            "stop_on_first_violation": True,
        },
    )
    cid = created.json()["id"]
    client.post(f"/api/campaigns/{cid}/start", json={"attestation": True})
    _wait_campaign(client, cid)

    conn = sqlite3.connect(api_db)
    rows = conn.execute(
        "SELECT type FROM events WHERE campaign_id = ?", (cid,)
    ).fetchall()
    types = {r[0] for r in rows}
    assert "campaign.started" in types
    assert "candidate.scored" in types
    conn.close()


def test_openai_agents_requires_project_path(client: TestClient):
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
        },
    )
    assert r.status_code == 400
    assert "project_path" in r.text


def test_legacy_openai_support_agent_target_rejected(client: TestClient):
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_support_agent",
        },
    )
    assert r.status_code == 422


def test_relative_project_path_resolves_to_sample(client: TestClient):
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": "examples/openai_support_agent",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    resolved = Path(body["config"]["project_path"])
    assert resolved.name == "openai_support_agent"
    assert (resolved / ".mutiny" / "adapter.py").is_file()
    # Milestone C: project_path upserts a project and links the campaign
    assert body.get("project_id")
    assert body.get("project", {}).get("path") == str(resolved)


def test_hosted_campaign_via_sample_project_path(client: TestClient, monkeypatch):
    """Hosted loads Adapter #1 sample via project_path — not allowlist magic."""
    monkeypatch.setenv("MUTINY_SAMPLE_OFFLINE", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    repo = Path(__file__).resolve().parents[2]
    sample = repo / "examples" / "openai_support_agent"
    assert (sample / ".mutiny" / "adapter.py").is_file()

    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 8,
            "max_generations": 3,
            "elite_count": 2,
            "stop_on_first_violation": True,
            "max_turns": 3,
            "rng_seed": 5,
            "use_boundary_seeds": True,
            "target": "openai_agents",
            "project_path": str(sample),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["config"]["target"] == "openai_agents"
    assert body["config"]["project_path"] == str(sample.resolve())

    cid = body["id"]
    started = client.post(
        f"/api/campaigns/{cid}/start", json={"attestation": True}
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"

    final = _wait_campaign(client, cid, timeout=60.0)
    assert final["status"] in {"violation", "completed", "failed"}
    assert final["status"] != "failed", final.get("metrics")
    # Sample + boundary seeds should find refund_limit under offline model
    assert final["status"] == "violation" or final.get("metrics", {}).get(
        "violated"
    )

    cands = client.get(f"/api/campaigns/{cid}/candidates")
    assert cands.status_code == 200
    assert len(cands.json()["candidates"]) >= 1


def test_projects_crud_and_campaign_list(client: TestClient):
    """Milestone C: projects as first-class entities + campaign history API."""
    empty = client.get("/api/projects")
    assert empty.status_code == 200
    assert empty.json()["projects"] == []

    created = client.post(
        "/api/projects",
        json={
            "path": "examples/openai_support_agent",
            "name": "Sample Support",
            "adapter": "openai_agents",
        },
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["name"] == "Sample Support"
    assert project["adapter"] == "openai_agents"
    assert Path(project["path"]).name == "openai_support_agent"
    pid = project["id"]

    # Idempotent register by path
    again = client.post(
        "/api/projects",
        json={"path": "examples/openai_support_agent"},
    )
    assert again.status_code == 201
    assert again.json()["id"] == pid

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert len(listed.json()["projects"]) == 1

    detail = client.get(f"/api/projects/{pid}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == pid
    assert body["current_adapter"] == "openai_agents"
    assert "policies" in body
    assert body["recent_campaigns"] == []
    assert body["last_run"] is None

    # Campaign via project_id
    camp = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_id": pid,
        },
    )
    assert camp.status_code == 201, camp.text
    camp_body = camp.json()
    assert camp_body["project_id"] == pid
    assert camp_body["project"]["id"] == pid
    assert "project_path" in camp_body["config"]

    # Campaign via project_path still upserts/links
    camp2 = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": "examples/openai_support_agent",
        },
    )
    assert camp2.status_code == 201, camp2.text
    assert camp2.json()["project_id"] == pid

    # Harness campaign has no project
    harness = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "in_process_demo",
        },
    )
    assert harness.status_code == 201
    assert harness.json().get("project_id") is None

    hist = client.get("/api/campaigns")
    assert hist.status_code == 200
    campaigns = hist.json()["campaigns"]
    assert len(campaigns) >= 3
    ids = {c["id"] for c in campaigns}
    assert camp_body["id"] in ids
    assert camp2.json()["id"] in ids
    assert harness.json()["id"] in ids
    for c in campaigns:
        assert "status" in c
        assert "created_at" in c
        assert "finished_at" in c or "completed_at" in c
        assert "generation" in c
        assert "violation" in c

    filtered = client.get("/api/campaigns", params={"project_id": pid})
    assert filtered.status_code == 200
    only_project = filtered.json()["campaigns"]
    assert len(only_project) == 2
    assert all(c["project_id"] == pid for c in only_project)

    # Alias filter
    alias = client.get("/api/campaigns", params={"project": pid})
    assert alias.status_code == 200
    assert len(alias.json()["campaigns"]) == 2

    detail2 = client.get(f"/api/projects/{pid}")
    assert detail2.status_code == 200
    assert len(detail2.json()["recent_campaigns"]) == 2
    assert detail2.json()["last_run"] is not None

    missing = client.get("/api/projects/does-not-exist")
    assert missing.status_code == 404

    bad = client.post(
        "/api/projects",
        json={"path": "/tmp/mutiny-not-a-real-project-dir"},
    )
    assert bad.status_code == 400


def test_schema_version_includes_projects(client: TestClient, api_db: Path):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["schema_version"] == "10"
    conn = sqlite3.connect(api_db)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "projects" in tables
    assert "test_runs" in tables
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()
    }
    assert "project_id" in cols
    conn.close()


def test_tests_run_persists_history_and_batch(client: TestClient):
    """Milestone D: test history, summary, batch run, delete."""
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 6,
            "max_generations": 4,
            "rng_seed": 0,
            "use_boundary_seeds": True,
            "stop_on_first_violation": True,
        },
    )
    assert created.status_code in {200, 201}
    cid = created.json()["id"]
    start = client.post(f"/api/campaigns/{cid}/start", json={"attestation": True})
    assert start.status_code == 200
    body = _wait_campaign(client, cid)
    assert body["status"] == "violation"

    cands = client.get(f"/api/campaigns/{cid}/candidates").json()["candidates"]
    violators = [c for c in cands if c.get("violated")]
    assert violators
    vid = violators[0]["id"]
    assert client.post(f"/api/candidates/{vid}/minimize", json={}).status_code == 200
    reg = client.post(
        f"/api/candidates/{vid}/regression",
        json={"name": "history_refund"},
    )
    assert reg.status_code == 201
    rid = reg.json()["id"]

    fail = client.post(
        "/api/tests/run", json={"regression_id": rid, "fixed_agent": False}
    )
    assert fail.status_code == 200
    assert fail.json()["status"] == "FAIL"
    assert fail.json()["run_id"]
    assert fail.json()["duration_ms"] is not None
    assert fail.json()["policy_version"]

    passed = client.post(
        "/api/tests/run", json={"regression_id": rid, "fixed_agent": True}
    )
    assert passed.status_code == 200
    assert passed.json()["status"] == "PASS"

    runs = client.get(f"/api/regressions/{rid}/runs")
    assert runs.status_code == 200
    assert len(runs.json()["runs"]) >= 2

    detail = client.get(f"/api/regressions/{rid}")
    assert detail.status_code == 200
    assert detail.json()["last_run"]["status"] == "PASS"
    assert len(detail.json()["runs"]) >= 2

    summary = client.get("/api/tests/summary")
    assert summary.status_code == 200
    assert summary.json()["regression_count"] >= 1
    assert summary.json()["pass_rate"] is not None

    batch = client.post("/api/tests/run", json={"run_all": True, "fixed_agent": True})
    assert batch.status_code == 200
    assert "results" in batch.json()
    assert batch.json()["passed"] >= 1

    listed = client.get("/api/regressions")
    assert listed.status_code == 200
    assert listed.json()["regressions"][0].get("last_run") is not None

    deleted = client.delete(f"/api/regressions/{rid}")
    assert deleted.status_code == 200
    assert client.get(f"/api/regressions/{rid}").status_code == 404
