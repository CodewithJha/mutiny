"""M-PR1→M-PR8E API: Hosted refuses arbitrary project_path adapter execution."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app


MARKER_NAME = "MUTINY_KILL_SWITCH_EXECUTED"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "test_mutiny.sqlite"


@pytest.fixture
def client(api_db: Path):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _malicious_project(tmp_path: Path) -> Path:
    mutiny = tmp_path / ".mutiny"
    mutiny.mkdir()
    marker = tmp_path / MARKER_NAME
    (mutiny / "adapter.py").write_text(
        f"""\
from pathlib import Path
Path({str(marker)!r}).write_text("executed", encoding="utf-8")

def create_adapter():
    raise RuntimeError("adapter factory must not run under M-PR8E")
""",
        encoding="utf-8",
    )
    (tmp_path / "policy.yaml").write_text(
        "version: '1'\ntarget: kill_switch_probe\nrules: []\n",
        encoding="utf-8",
    )
    return tmp_path


def test_a_create_campaign_rejects_arbitrary_project_exec(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/campaigns must not exec customer adapter; clear 410."""
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME

    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": str(project),
        },
    )
    assert r.status_code == 410, r.text
    body = r.json()
    assert body["error"]["code"] == "hosted_customer_execution_removed"
    assert "removed" in body["error"]["message"].lower()
    assert not marker.exists(), "adapter.py must not have been executed"


def test_b_start_and_project_id_cannot_bypass(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """project_id / start / tests paths cannot bypass removal."""
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME

    created = client.post(
        "/api/projects",
        json={"path": str(project), "name": "Probe"},
    )
    assert created.status_code == 201, created.text
    assert not marker.exists()
    pid = created.json()["id"]

    via_id = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_id": pid,
        },
    )
    assert via_id.status_code == 410, via_id.text
    assert via_id.json()["error"]["code"] == "hosted_customer_execution_removed"
    assert not marker.exists()

    harness = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "in_process_demo",
        },
    )
    assert harness.status_code == 201
    assert not marker.exists()


def test_c_trusted_demo_campaign_still_works(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """in_process_demo harness remains usable; ALLOW flag irrelevant."""
    import time

    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "elite_count": 1,
            "stop_on_first_violation": True,
            "max_turns": 2,
            "rng_seed": 0,
            "target": "in_process_demo",
        },
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    started = client.post(
        f"/api/campaigns/{cid}/start", json={"attestation": True}
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"

    deadline = time.time() + 30.0
    while time.time() < deadline:
        body = client.get(f"/api/campaigns/{cid}").json()
        if body["status"] not in {"created", "running"}:
            assert body["status"] in {"violation", "completed", "failed"}
            return
        time.sleep(0.05)
    raise AssertionError("demo campaign did not finish")


def test_meta_advertises_removal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    meta = client.get("/api/meta").json()
    safety = meta["safety"]
    assert safety.get("hosted_customer_adapter_exec") is False
    assert safety.get("hosted_customer_execution") == "removed"
    health = client.get("/api/health").json()
    assert health["adapter_loading"] == "trusted_demo_only"
