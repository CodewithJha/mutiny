"""Hosted stopping or restarting while an in-process campaign is running."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest
from demo_agent import DemoSupportAgent, InProcessDemoAdapter
from fastapi.testclient import TestClient
from mutiny_api.app import create_app
from mutiny_api.supervisor import INTERRUPTED_REASON

LONG_CAMPAIGN = {
    "population_size": 12,
    "max_generations": 8,
    "elite_count": 2,
    "stop_on_first_violation": False,
}


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "shutdown.sqlite"


def _start(client: TestClient, config: dict | None = None) -> str:
    created = client.post("/api/campaigns", json=config or LONG_CAMPAIGN)
    assert created.status_code == 201
    campaign_id = created.json()["id"]
    started = client.post(
        f"/api/campaigns/{campaign_id}/start", json={"attestation": True}
    )
    assert started.status_code == 200, started.text
    return campaign_id


def _rows(db: Path, sql: str, *params: object) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _slow_adapter(monkeypatch: pytest.MonkeyPatch, gate: threading.Event | None = None):
    """Make each agent step slow, or block it on *gate*, so a campaign is in flight."""
    entered = threading.Event()

    class SlowAdapter(InProcessDemoAdapter):
        def step(self, session_id, user_message):
            entered.set()
            if gate is None:
                time.sleep(0.02)
            else:
                gate.wait(timeout=10)
            return super().step(session_id, user_message)

    monkeypatch.setattr(
        "mutiny_api.supervisor._make_adapter",
        lambda cfg, **_: SlowAdapter(agent=DemoSupportAgent()),
    )
    return entered


def test_stopping_hosted_during_a_campaign_fails_the_campaign(
    api_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = _slow_adapter(monkeypatch)
    with TestClient(create_app(api_db)) as client:
        campaign_id = _start(client)
        assert entered.wait(timeout=5)

    status, metrics = _rows(
        api_db, "SELECT status, metrics_json FROM campaigns WHERE id = ?", campaign_id
    )[0]
    assert status == "failed"
    assert INTERRUPTED_REASON in metrics
    errors = _rows(
        api_db,
        "SELECT payload_json FROM events WHERE campaign_id = ? AND type = 'campaign.error'",
        campaign_id,
    )
    assert len(errors) == 1 and INTERRUPTED_REASON in errors[0][0]


def test_campaign_left_running_by_a_dead_process_is_failed_on_startup(
    api_db: Path,
) -> None:
    with TestClient(create_app(api_db)) as client:
        orphan = client.post("/api/campaigns", json=LONG_CAMPAIGN).json()["id"]
        client.app.state.repo.update_campaign_status(
            orphan, "running", metrics={"phase": "searching", "candidates_scored": 3}
        )
        # Simulate a killed process: nothing gets to tidy the row up.
        client.app.state.supervisor.shutdown = _no_shutdown

    assert _rows(api_db, "SELECT status FROM campaigns") == [("running",)]

    with TestClient(create_app(api_db)) as client:
        campaign = client.get(f"/api/campaigns/{orphan}").json()
        assert campaign["status"] == "failed"
        assert campaign["completed_at"] is not None
        assert campaign["metrics"]["error"] == INTERRUPTED_REASON
        assert campaign["metrics"]["candidates_scored"] == 3
        events = client.app.state.repo.list_events(orphan)
        assert [e["type"] for e in events] == ["campaign.error"]
        assert events[0]["payload"] == {"error": INTERRUPTED_REASON}

        health = client.get("/api/health").json()
        assert health["running_campaigns"] == 0
        assert health["status"] == "ok"

        # The single execution slot is free again.
        _start(client, {"population_size": 2, "max_generations": 1, "elite_count": 1})


async def _no_shutdown(timeout: float | None = None) -> bool:
    return True


def test_shutdown_stops_waiting_for_a_campaign_stuck_in_an_agent_step(
    api_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = threading.Event()
    entered = _slow_adapter(monkeypatch, gate)
    with TestClient(create_app(api_db)) as client:
        campaign_id = _start(client)
        assert entered.wait(timeout=5)
        supervisor = client.app.state.supervisor

        began = time.monotonic()
        assert client.portal.call(supervisor.shutdown, 0.05) is False
        assert time.monotonic() - began < 2

        gate.set()
        assert client.portal.call(supervisor.shutdown, 5.0) is True
        campaign = client.get(f"/api/campaigns/{campaign_id}").json()
        assert campaign["status"] == "failed"
        assert campaign["metrics"]["reason"] == INTERRUPTED_REASON


def test_repository_close_waits_for_an_in_flight_call(api_db: Path) -> None:
    """Closing SQLite under a running statement crashes the interpreter."""
    with TestClient(create_app(api_db)) as client:
        repo = client.app.state.repo
        closed = threading.Event()

        def close() -> None:
            repo.close()
            closed.set()

        repo._lock.acquire()
        closer = threading.Thread(target=close)
        try:
            closer.start()
            assert not closed.wait(timeout=0.1)
            repo.ping()
        finally:
            repo._lock.release()
        closer.join(timeout=1)
        assert closed.is_set()
        with pytest.raises(sqlite3.ProgrammingError):
            repo.ping()
        # Lifespan shutdown closes again; a second close is a no-op.
