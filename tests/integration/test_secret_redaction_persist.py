"""M-PR3: secret redaction across persistence, API, and CLI surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_api.db import connect
from mutiny_api.repository import Repository
from mutiny_cli.test_cmd import CaseResult
from mutiny_cli.test_cmd import TestReport as CliTestReport
from mutiny_cli.test_cmd import _evidence_from_replay
from mutiny_core.redact import REDACTED
from mutiny_core.trace import ExecutionTrace, ToolCall


FAKE_SECRET = "MUTINY_TEST_FAKE_SECRET_9f83c1"


def _trace_with_secret() -> dict:
    return {
        "candidate_id": "cand-secret",
        "session_id": "sess-secret",
        "turns": [
            {
                "user_message": "please refund",
                "assistant_message": "ok",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "name": "issue_refund",
                        "arguments": {
                            "order_id": "ord_1001",
                            "amount": 500,
                            "approved": False,
                            "api_key": FAKE_SECRET,
                            "password": FAKE_SECRET,
                        },
                    }
                ],
                "tool_results": [
                    {
                        "meta": f"Authorization: Bearer {FAKE_SECRET}",
                    }
                ],
                "raw": None,
            }
        ],
        "all_tool_calls": [
            {
                "id": "tc1",
                "name": "issue_refund",
                "arguments": {
                    "order_id": "ord_1001",
                    "amount": 500,
                    "api_key": FAKE_SECRET,
                },
            }
        ],
        "policy_hits": [],
        "fitness": 1.0,
        "status": "violator",
        "error": None,
        "model_info": {},
        "token_usage": {},
    }


def _seed_candidate(repo: Repository) -> str:
    camp = repo.create_campaign(
        "camp-secret",
        {"target": "in_process_demo", "population_size": 1},
    )
    cid = "cand-secret"
    repo.upsert_candidate(
        candidate_id=cid,
        campaign_id=camp["id"],
        parent_id=None,
        generation=0,
        genome={"id": cid, "messages": []},
        fitness=1.0,
        status="violator",
        violated=True,
        hits=[
            {
                "rule_id": "refund_limit",
                "violated": True,
                "evidence": {
                    "rule_id": "refund_limit",
                    "message": "hit",
                    "arguments": {"api_key": FAKE_SECRET, "amount": 500},
                },
                "proximity": 1.0,
            }
        ],
    )
    return cid


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "redact_mutiny.sqlite"


@pytest.fixture
def client(api_db: Path):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def test_h_persistence_boundary(api_db: Path) -> None:
    """Persisted SQLite trace/hits must not contain the fake secret."""
    conn = connect(api_db)
    repo = Repository(conn)
    cid = _seed_candidate(repo)
    repo.upsert_trace(cid, _trace_with_secret())
    repo.append_event(
        "camp-secret",
        "candidate_scored",
        {"trace": _trace_with_secret(), "api_key": FAKE_SECRET},
    )
    repo.save_test_run(
        "run-secret",
        regression_id=_ensure_regression(repo),
        status="FAIL",
        duration_ms=1.0,
        policy_version="1",
        agent_version=None,
        fixed_agent=False,
        violated_rule_ids=["refund_limit"],
        evidence=[{"tool": "issue_refund", "arguments": {"token": FAKE_SECRET}}],
        summary="probe",
    )

    stored = repo.get_candidate(cid)
    assert stored is not None
    blob = json.dumps(stored)
    assert FAKE_SECRET not in blob
    assert stored["trace"]["all_tool_calls"][0]["arguments"]["api_key"] == REDACTED
    assert stored["hits"][0]["evidence"]["arguments"]["api_key"] == REDACTED

    raw_trace = conn.execute(
        "SELECT trace_json FROM traces WHERE candidate_id = ?", (cid,)
    ).fetchone()[0]
    assert FAKE_SECRET not in raw_trace

    raw_event = conn.execute(
        "SELECT payload_json FROM events WHERE campaign_id = ?",
        ("camp-secret",),
    ).fetchone()[0]
    assert FAKE_SECRET not in raw_event

    raw_run = conn.execute(
        "SELECT evidence_json FROM test_runs WHERE id = ?",
        ("run-secret",),
    ).fetchone()[0]
    assert FAKE_SECRET not in raw_run
    conn.close()


def _ensure_regression(repo: Repository) -> str:
    row = repo.save_regression(
        "reg-secret",
        campaign_id="camp-secret",
        candidate_id="cand-secret",
        path=None,
        artifact={
            "version": "1",
            "name": "secret_probe",
            "target": "in_process_demo",
            "policy_rule_ids": ["refund_limit"],
            "conversation": ["hi"],
            "expected": {"must_not_violate": ["refund_limit"]},
            "provenance": {
                "minimized_from_turns": 1,
                "minimized_turn_count": 1,
                "rule_ids": ["refund_limit"],
            },
        },
    )
    return row["id"]


def test_i_api_evidence_boundary(client: TestClient) -> None:
    """API candidate/trace responses must not expose the fake secret."""
    repo: Repository = client.app.state.repo
    cid = _seed_candidate(repo)
    repo.upsert_trace(cid, _trace_with_secret())

    r = client.get(f"/api/candidates/{cid}")
    assert r.status_code == 200
    body = r.json()
    blob = json.dumps(body)
    assert FAKE_SECRET not in blob
    assert body["trace"]["turns"][0]["tool_calls"][0]["arguments"]["api_key"] == REDACTED


def test_j_cli_evidence_boundary(tmp_path: Path) -> None:
    """CLI evidence extracted from replay traces must be redacted."""
    trace = ExecutionTrace(
        candidate_id="cli",
        session_id="cli",
        all_tool_calls=[
            ToolCall(
                id="1",
                name="issue_refund",
                arguments={
                    "api_key": FAKE_SECRET,
                    "password": FAKE_SECRET,
                    "amount": 500,
                },
            )
        ],
    )
    replay = SimpleNamespace(trace=trace)
    evidence = _evidence_from_replay(replay)  # type: ignore[arg-type]
    blob = json.dumps(evidence)
    assert FAKE_SECRET not in blob
    assert evidence[0]["arguments"]["api_key"] == REDACTED
    assert evidence[0]["arguments"]["amount"] == 500

    report = CliTestReport(
        generated_at="2026-09-09T00:00:00Z",
        project=str(tmp_path),
        policy_version="1",
        results=[
            CaseResult(
                id="probe",
                name="probe",
                path="probe.json",
                status="FAIL",
                duration_ms=1.0,
                policy_version="1",
                rule_ids=["refund_limit"],
                violated_rule_ids=["refund_limit"],
                evidence=evidence,
                summary="fail",
            )
        ],
        passed=0,
        failed=1,
        skipped=0,
    )
    out_path = tmp_path / "report.json"
    out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    assert FAKE_SECRET not in out_path.read_text(encoding="utf-8")


def test_e2e_fake_secret_absent_from_all_surfaces(client: TestClient) -> None:
    """Security regression: MUTINY_TEST_FAKE_SECRET_9f83c1 never survives Mutiny surfaces."""
    repo: Repository = client.app.state.repo
    cid = _seed_candidate(repo)
    repo.upsert_trace(cid, _trace_with_secret())
    repo.append_event(
        "camp-secret",
        "candidate_scored",
        {
            "candidate_id": cid,
            "trace": _trace_with_secret(),
            "hits": [
                {
                    "evidence": {
                        "arguments": {"access_token": FAKE_SECRET},
                        "message": f"Authorization: Bearer {FAKE_SECRET}",
                    }
                }
            ],
        },
    )

    api_body = client.get(f"/api/candidates/{cid}").json()
    events = repo.list_events("camp-secret")

    surfaces = [
        json.dumps(api_body),
        json.dumps(events),
        json.dumps(repo.get_candidate(cid)),
    ]
    for surface in surfaces:
        assert FAKE_SECRET not in surface, surface[:500]
