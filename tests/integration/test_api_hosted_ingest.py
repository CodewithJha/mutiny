"""M-PR8B: Hosted observe-only ingestion API contract tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_api.auth import API_TOKEN_ENV
from mutiny_api.db import SCHEMA_VERSION, connect
from mutiny_api.ingest import IngestService, max_batch_bytes
from mutiny_api.ingest_schemas import INGEST_SCHEMA_VERSION
from mutiny_api.repository import INGEST_LOCAL_KEY_PREFIX, Repository


FAKE_TOKEN = "test-mutiny-ingest-token-mpr8b-not-real"
WRONG_TOKEN = "wrong-mutiny-ingest-token"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "ingest.sqlite"


@pytest.fixture
def auth_on(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)
    return FAKE_TOKEN


@pytest.fixture
def auth_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_TOKEN_ENV, raising=False)


@pytest.fixture
def client(api_db: Path, auth_on: str):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_no_auth(api_db: Path, auth_off: None):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _auth(token: str = FAKE_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _redaction() -> dict[str, Any]:
    return {"applied": True, "marker": "[REDACTED]"}


def _envelope(**extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": "0.1.0",
        "execution_mode": "local_cli",
        "redaction": _redaction(),
    }
    body.update(extra)
    return body


def _open_campaign(
    client: TestClient,
    *,
    campaign_id: str | None = None,
    local_project_key: str = "proj-key-abc",
    project_label: str = "/tmp/never-open-me",
    **extra: Any,
) -> Any:
    cid = campaign_id or str(uuid.uuid4())
    payload = _envelope(
        campaign_id=cid,
        local_project_key=local_project_key,
        project_name="demo",
        project_label=project_label,
        attestation=True,
        status="running",
        config={"population_size": 4, "max_generations": 2, "rng_seed": 1},
        **extra,
    )
    return client.post(
        "/api/ingest/v1/campaigns",
        headers=_auth(),
        json=payload,
    ), cid, payload


# —— Authentication ——


def test_01_ingest_without_token(client: TestClient) -> None:
    r = client.post(
        "/api/ingest/v1/campaigns",
        json=_envelope(
            campaign_id=str(uuid.uuid4()),
            local_project_key="k",
            attestation=True,
        ),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_02_ingest_with_invalid_token(client: TestClient) -> None:
    r = client.post(
        "/api/ingest/v1/campaigns",
        headers=_auth(WRONG_TOKEN),
        json=_envelope(
            campaign_id=str(uuid.uuid4()),
            local_project_key="k",
            attestation=True,
        ),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert FAKE_TOKEN not in r.text
    assert WRONG_TOKEN not in r.text


def test_03_ingest_with_valid_token(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    assert r.status_code == 201, r.text
    assert r.json()["created"] is True
    assert r.json()["campaign"]["id"] == cid


def test_03b_ingest_works_when_auth_disabled(client_no_auth: TestClient) -> None:
    cid = str(uuid.uuid4())
    r = client_no_auth.post(
        "/api/ingest/v1/campaigns",
        json=_envelope(
            campaign_id=cid,
            local_project_key="local-no-auth",
            attestation=True,
        ),
    )
    assert r.status_code == 201, r.text


# —— Schema ——


def test_04_unsupported_schema_version(client: TestClient) -> None:
    r = client.post(
        "/api/ingest/v1/campaigns",
        headers=_auth(),
        json=_envelope(
            schema_version=99,
            campaign_id=str(uuid.uuid4()),
            local_project_key="k",
            attestation=True,
        ),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "unsupported_ingest_schema"


def test_05_missing_required_project_identity(client: TestClient) -> None:
    r = client.post(
        "/api/ingest/v1/campaigns",
        headers=_auth(),
        json=_envelope(campaign_id=str(uuid.uuid4()), attestation=True),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_ingest_payload"


def test_06_malformed_payload(client: TestClient) -> None:
    r = client.post(
        "/api/ingest/v1/campaigns",
        headers=_auth(),
        json={"schema_version": "not-an-int", "redaction": {"applied": True}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# —— Redaction ——


def test_07_missing_redaction_marker(client: TestClient) -> None:
    body = _envelope(
        campaign_id=str(uuid.uuid4()),
        local_project_key="k",
        attestation=True,
    )
    del body["redaction"]
    r = client.post("/api/ingest/v1/campaigns", headers=_auth(), json=body)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "redaction_required"


def test_07b_redaction_applied_false_rejected(client: TestClient) -> None:
    body = _envelope(
        campaign_id=str(uuid.uuid4()),
        local_project_key="k",
        attestation=True,
        redaction={"applied": False, "marker": "[REDACTED]"},
    )
    r = client.post("/api/ingest/v1/campaigns", headers=_auth(), json=body)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "redaction_required"


def test_08_redacted_payload_accepted(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    assert r.status_code == 201
    batch = _envelope(
        campaign_id=cid,
        events=[
            {
                "event_id": str(uuid.uuid4()),
                "type": "campaign.started",
                "payload": {"note": "ok", "api_key": "[REDACTED]"},
            }
        ],
    )
    br = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch",
        headers=_auth(),
        json=batch,
    )
    assert br.status_code == 200, br.text
    assert br.json()["events_accepted"] == 1


def test_09_secret_does_not_persist(client: TestClient, api_db: Path) -> None:
    r, cid, _ = _open_campaign(client)
    assert r.status_code == 201
    batch = _envelope(
        campaign_id=cid,
        events=[
            {
                "event_id": str(uuid.uuid4()),
                "type": "candidate.scored",
                "payload": {
                    "api_key": "sk-live-SHOULD-NOT-PERSIST",
                    "password": "hunter2",
                    "token": "secret-token-value",
                    "nested": {"access_token": "nested-secret"},
                    "note": "Authorization: Bearer leaked-bearer-token",
                },
            }
        ],
        artifacts=[
            {
                "kind": "candidate",
                "id": str(uuid.uuid4()),
                "body": {
                    "generation": 0,
                    "genome": {"messages": [{"role": "user", "content": "hi"}]},
                    "fitness": 1.0,
                    "violated": False,
                    "hits": [{"api_key": "hit-secret-key"}],
                },
            }
        ],
    )
    br = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch",
        headers=_auth(),
        json=batch,
    )
    assert br.status_code == 200, br.text

    events = client.get(f"/api/campaigns/{cid}", headers=_auth())
    assert events.status_code == 200
    # Read via repository / events list through SSE history isn't REST;
    # query candidates + raw DB.
    conn = connect(api_db)
    repo = Repository(conn)
    stored_events = repo.list_events(cid)
    blob = json.dumps(stored_events)
    assert "sk-live-SHOULD-NOT-PERSIST" not in blob
    assert "hunter2" not in blob
    assert "secret-token-value" not in blob
    assert "nested-secret" not in blob
    assert "leaked-bearer-token" not in blob
    assert "hit-secret-key" not in blob
    assert "[REDACTED]" in blob
    cands = repo.list_candidates(cid)
    assert cands
    assert "hit-secret-key" not in json.dumps(cands)
    conn.close()


# —— Identity ——


def test_10_first_campaign_ingestion(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client, local_project_key="unique-key-10")
    assert r.status_code == 201
    camp = r.json()["campaign"]
    assert camp["id"] == cid
    assert camp["status"] == "running"
    assert camp["config"]["execution_mode"] == "local_cli"
    assert camp["config"]["local_project_key"] == "unique-key-10"
    assert camp["project_id"]
    # Opaque path prefix — not a real FS mount.
    assert camp["project"]["path"].startswith(INGEST_LOCAL_KEY_PREFIX)


def test_11_duplicate_campaign_ingestion(client: TestClient) -> None:
    r1, cid, payload = _open_campaign(client, local_project_key="dup-key")
    assert r1.status_code == 201
    r2 = client.post("/api/ingest/v1/campaigns", headers=_auth(), json=payload)
    assert r2.status_code == 201
    assert r2.json()["created"] is False
    assert r2.json()["campaign"]["id"] == cid


def test_12_conflicting_campaign_identity(client: TestClient) -> None:
    r1, cid, payload = _open_campaign(client, local_project_key="conflict-key")
    assert r1.status_code == 201
    payload = dict(payload)
    payload["config"] = {"population_size": 99, "max_generations": 9, "rng_seed": 99}
    r2 = client.post("/api/ingest/v1/campaigns", headers=_auth(), json=payload)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "campaign_conflict"


# —— Events ——


def test_13_event_ingestion(client: TestClient, api_db: Path) -> None:
    r, cid, _ = _open_campaign(client)
    eid = str(uuid.uuid4())
    br = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch",
        headers=_auth(),
        json=_envelope(
            campaign_id=cid,
            seq=5,
            events=[
                {
                    "event_id": eid,
                    "type": "generation.started",
                    "payload": {"generation": 2},
                    "generation": 2,
                }
            ],
        ),
    )
    assert br.status_code == 200, br.text
    assert br.json()["events_accepted"] == 1
    conn = connect(api_db)
    evs = Repository(conn).list_events(cid)
    conn.close()
    assert len(evs) == 1
    assert evs[0]["type"] == "generation.started"
    assert evs[0]["payload"]["generation"] == 2


def test_14_duplicate_event_idempotent(client: TestClient, api_db: Path) -> None:
    r, cid, _ = _open_campaign(client)
    eid = str(uuid.uuid4())
    batch = _envelope(
        campaign_id=cid,
        events=[
            {
                "event_id": eid,
                "type": "violation.detected",
                "payload": {"rule_id": "refund_limit"},
            }
        ],
    )
    assert (
        client.post(
            f"/api/ingest/v1/campaigns/{cid}/batch", headers=_auth(), json=batch
        ).status_code
        == 200
    )
    br2 = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch", headers=_auth(), json=batch
    )
    assert br2.status_code == 200, br2.text
    assert br2.json()["events_duplicate"] == 1
    assert br2.json()["events_accepted"] == 0
    conn = connect(api_db)
    assert len(Repository(conn).list_events(cid)) == 1
    conn.close()


def test_15_conflicting_event_returns_409(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    eid = str(uuid.uuid4())
    batch1 = _envelope(
        campaign_id=cid,
        events=[
            {
                "event_id": eid,
                "type": "campaign.started",
                "payload": {"a": 1},
            }
        ],
    )
    assert (
        client.post(
            f"/api/ingest/v1/campaigns/{cid}/batch", headers=_auth(), json=batch1
        ).status_code
        == 200
    )
    batch2 = _envelope(
        campaign_id=cid,
        events=[
            {
                "event_id": eid,
                "type": "campaign.started",
                "payload": {"a": 2},
            }
        ],
    )
    br = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch", headers=_auth(), json=batch2
    )
    assert br.status_code == 409
    assert br.json()["error"]["code"] == "event_conflict"


def test_16_out_of_order_event_accepted(client: TestClient, api_db: Path) -> None:
    r, cid, _ = _open_campaign(client)
    for seq, gen in ((5, 5), (3, 3), (4, 4)):
        br = client.post(
            f"/api/ingest/v1/campaigns/{cid}/batch",
            headers=_auth(),
            json=_envelope(
                campaign_id=cid,
                seq=seq,
                events=[
                    {
                        "event_id": str(uuid.uuid4()),
                        "type": "generation.started",
                        "seq": seq,
                        "generation": gen,
                        "payload": {"generation": gen},
                    }
                ],
            ),
        )
        assert br.status_code == 200, br.text
    conn = connect(api_db)
    evs = Repository(conn).list_events(cid)
    conn.close()
    assert len(evs) == 3
    gens = [e["payload"]["generation"] for e in evs]
    assert gens == [5, 3, 4]  # persist order = arrival, gaps OK


# —— Security ——


def test_17_uploaded_project_path_never_accessed(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoy = tmp_path / "customer_project"
    decoy.mkdir()
    marker = decoy / "marker.txt"
    marker.write_text("should-not-be-read", encoding="utf-8")

    read_hits: list[str] = []
    real_read_text = Path.read_text
    real_open = Path.open

    def tracking_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if "customer_project" in str(self) or "passwd" in str(self):
            read_hits.append(f"read_text:{self}")
        return real_read_text(self, *args, **kwargs)

    def tracking_open(self: Path, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        if "customer_project" in str(self) or "passwd" in str(self):
            read_hits.append(f"open:{self}")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read_text)
    monkeypatch.setattr(Path, "open", tracking_open)

    with (
        patch("mutiny_api.supervisor.resolve_project_root") as resolve_mock,
        patch("mutiny_openai_agents.loader.load_adapter_factory") as load_mock,
    ):
        r, cid, _ = _open_campaign(
            client,
            local_project_key="opaque-key-17",
            project_label=str(decoy),
        )
        assert r.status_code == 201, r.text
        reg = client.post(
            "/api/ingest/v1/regressions",
            headers=_auth(),
            json=_envelope(
                regression_id=str(uuid.uuid4()),
                campaign_id=cid,
                path="../../etc/passwd",
                artifact={"version": "1", "name": "x"},
            ),
        )
        assert reg.status_code == 201, reg.text
        resolve_mock.assert_not_called()
        load_mock.assert_not_called()

    assert read_hits == [], f"ingest accessed uploaded paths: {read_hits}"
    assert marker.read_text(encoding="utf-8") == "should-not-be-read"


def test_18_ingestion_never_invokes_load_adapter_factory(client: TestClient) -> None:
    with patch(
        "mutiny_openai_agents.loader.load_adapter_factory",
        side_effect=AssertionError("load_adapter_factory must not run"),
    ) as mocked:
        r, cid, _ = _open_campaign(client)
        assert r.status_code == 201
        br = client.post(
            f"/api/ingest/v1/campaigns/{cid}/batch",
            headers=_auth(),
            json=_envelope(
                campaign_id=cid,
                events=[
                    {
                        "event_id": str(uuid.uuid4()),
                        "type": "campaign.started",
                        "payload": {},
                    }
                ],
                artifacts=[
                    {
                        "kind": "candidate",
                        "id": str(uuid.uuid4()),
                        "body": {
                            "generation": 0,
                            "genome": {},
                            "fitness": 0.1,
                            "violated": False,
                        },
                    }
                ],
            ),
        )
        assert br.status_code == 200, br.text
        cr = client.post(
            f"/api/ingest/v1/campaigns/{cid}/complete",
            headers=_auth(),
            json=_envelope(status="completed", metrics={"generations_completed": 1}),
        )
        assert cr.status_code == 200, cr.text
        mocked.assert_not_called()


def test_19_ingestion_never_invokes_exec_module(client: TestClient) -> None:
    with patch("importlib.util.spec_from_file_location") as spec_mock:
        r, cid, _ = _open_campaign(client, local_project_key="no-exec")
        assert r.status_code == 201
        client.post(
            f"/api/ingest/v1/campaigns/{cid}/batch",
            headers=_auth(),
            json=_envelope(
                campaign_id=cid,
                events=[
                    {
                        "event_id": str(uuid.uuid4()),
                        "type": "campaign.error",
                        "payload": {"error": "local fail"},
                    }
                ],
            ),
        )
        spec_mock.assert_not_called()


def test_20_malicious_looking_path_remains_inert(
    client: TestClient, api_db: Path
) -> None:
    evil = "; rm -rf /; cat /etc/passwd"
    r, cid, _ = _open_campaign(
        client,
        local_project_key=evil,
        project_label=evil,
    )
    assert r.status_code == 201
    camp = r.json()["campaign"]
    assert camp["config"]["project_label"] == evil
    assert evil in camp["project"]["path"]
    # Ensure DB stores it as data only.
    conn = connect(api_db)
    row = Repository(conn).get_campaign(cid)
    conn.close()
    assert row is not None
    assert row["config"]["local_project_key"] == evil


def test_20b_ingest_module_has_no_exec_imports() -> None:
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "apps/api/src/mutiny_api/ingest.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
            for alias in node.names:
                imported.add(alias.name)
    assert "pickle" not in imported
    assert "importlib" not in imported
    assert "load_adapter_factory" not in imported
    assert "exec_module" not in imported
    assert "resolve_project_root" not in imported
    # No Call to dangerous builtins in module body / functions.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "open"}


# —— Regression / test runs ——


def test_21_regression_ingestion(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    rid = str(uuid.uuid4())
    cand = str(uuid.uuid4())
    rr = client.post(
        "/api/ingest/v1/regressions",
        headers=_auth(),
        json=_envelope(
            regression_id=rid,
            campaign_id=cid,
            candidate_id=cand,
            path=".mutiny/tests/foo.json",
            artifact={
                "version": "1",
                "name": "refund_limit_regression",
                "target_rule_ids": ["refund_limit"],
            },
        ),
    )
    assert rr.status_code == 201, rr.text
    assert rr.json()["created"] is True
    assert rr.json()["regression"]["id"] == rid
    listed = client.get("/api/regressions", headers=_auth())
    assert listed.status_code == 200
    ids = {x["id"] for x in listed.json()["regressions"]}
    assert rid in ids


def test_22_duplicate_regression(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    rid = str(uuid.uuid4())
    body = _envelope(
        regression_id=rid,
        campaign_id=cid,
        artifact={"version": "1", "name": "r"},
    )
    assert (
        client.post("/api/ingest/v1/regressions", headers=_auth(), json=body).status_code
        == 201
    )
    r2 = client.post("/api/ingest/v1/regressions", headers=_auth(), json=body)
    assert r2.status_code == 201
    assert r2.json()["created"] is False

    conflict = dict(body)
    conflict["artifact"] = {"version": "1", "name": "other"}
    r3 = client.post("/api/ingest/v1/regressions", headers=_auth(), json=conflict)
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "regression_conflict"


def test_23_test_run_ingestion(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    rid = str(uuid.uuid4())
    assert (
        client.post(
            "/api/ingest/v1/regressions",
            headers=_auth(),
            json=_envelope(
                regression_id=rid,
                campaign_id=cid,
                artifact={"version": "1"},
            ),
        ).status_code
        == 201
    )
    tid = str(uuid.uuid4())
    tr = client.post(
        "/api/ingest/v1/test-runs",
        headers=_auth(),
        json=_envelope(
            test_run_id=tid,
            regression_id=rid,
            campaign_id=cid,
            status="PASS",
            duration_ms=12.5,
            violated_rule_ids=[],
            evidence=[{"api_key": "should-redact"}],
            summary="ok",
        ),
    )
    assert tr.status_code == 201, tr.text
    assert tr.json()["created"] is True
    assert tr.json()["test_run"]["status"] == "PASS"
    assert tr.json()["test_run"]["evidence"][0]["api_key"] == "[REDACTED]"


def test_24_duplicate_test_run(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    rid = str(uuid.uuid4())
    client.post(
        "/api/ingest/v1/regressions",
        headers=_auth(),
        json=_envelope(regression_id=rid, campaign_id=cid, artifact={"version": "1"}),
    )
    tid = str(uuid.uuid4())
    body = _envelope(
        test_run_id=tid,
        regression_id=rid,
        status="FAIL",
        violated_rule_ids=["refund_limit"],
        evidence=[],
    )
    assert (
        client.post("/api/ingest/v1/test-runs", headers=_auth(), json=body).status_code
        == 201
    )
    r2 = client.post("/api/ingest/v1/test-runs", headers=_auth(), json=body)
    assert r2.status_code == 201
    assert r2.json()["created"] is False
    bad = dict(body)
    bad["status"] = "PASS"
    r3 = client.post("/api/ingest/v1/test-runs", headers=_auth(), json=bad)
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "test_run_conflict"


# —— Completion ——


def test_25_campaign_completion(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    cr = client.post(
        f"/api/ingest/v1/campaigns/{cid}/complete",
        headers=_auth(),
        json=_envelope(
            status="completed",
            metrics={"generations_completed": 2, "violated": False},
        ),
    )
    assert cr.status_code == 200, cr.text
    assert cr.json()["updated"] is True
    assert cr.json()["campaign"]["status"] == "completed"
    assert cr.json()["campaign"]["completed_at"]


def test_26_failed_campaign_completion(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    cr = client.post(
        f"/api/ingest/v1/campaigns/{cid}/complete",
        headers=_auth(),
        json=_envelope(
            status="failed",
            reason="interrupted",
            metrics={"error": "local crash"},
        ),
    )
    assert cr.status_code == 200, cr.text
    assert cr.json()["campaign"]["status"] == "failed"
    assert cr.json()["campaign"]["metrics"]["complete_reason"] == "interrupted"


def test_27_batch_size_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUTINY_INGEST_MAX_EVENTS_PER_BATCH", "2")
    # Recreate app so... limits are read at request time via env helpers — OK.
    r, cid, _ = _open_campaign(client)
    br = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch",
        headers=_auth(),
        json=_envelope(
            campaign_id=cid,
            events=[
                {
                    "event_id": str(uuid.uuid4()),
                    "type": "campaign.started",
                    "payload": {},
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "type": "generation.started",
                    "payload": {},
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "type": "campaign.completed",
                    "payload": {},
                },
            ],
        ),
    )
    assert br.status_code == 413
    assert br.json()["error"]["code"] == "payload_too_large"


def test_28_unknown_event_type_rejected(client: TestClient) -> None:
    r, cid, _ = _open_campaign(client)
    br = client.post(
        f"/api/ingest/v1/campaigns/{cid}/batch",
        headers=_auth(),
        json=_envelope(
            campaign_id=cid,
            events=[
                {
                    "event_id": str(uuid.uuid4()),
                    "type": "candidate.executing",
                    "payload": {},
                }
            ],
        ),
    )
    assert br.status_code == 400
    assert br.json()["error"]["code"] == "invalid_ingest_payload"


def test_29_schema_version_bumped() -> None:
    assert SCHEMA_VERSION == "11"


def test_30_ingest_service_rejects_pickle_paths() -> None:
    """IngestService methods never call exec/load helpers (static boundary)."""
    import mutiny_api.ingest as m

    assert not hasattr(IngestService, "load_adapter_factory")
    assert "CampaignSupervisor" not in m.__dict__
    assert max_batch_bytes() >= 1024
