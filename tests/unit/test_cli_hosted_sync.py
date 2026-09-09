"""M-PR8C: CLI local execution + Hosted observe-only sync."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from mutiny_cli import hosted_sync, run_cmd
from mutiny_cli.hosted_sync import (
    SYNC_FAILED_EXIT,
    HostedIngestClient,
    HostedSyncError,
    LocalRunBundle,
    RedactionDisabledError,
    SyncOutcome,
    auth_headers_from_env,
    build_batch_payload,
    build_campaign_open_payload,
    build_complete_payload,
    build_ingest_events,
    build_regression_payload,
    build_test_run_payload,
    ensure_redaction_allowed_for_upload,
    local_project_key,
    sync_local_campaign,
    terminal_status,
)
from mutiny_cli.main import main
from mutiny_core.campaign.engine import CampaignResult, ScoredCandidate
from mutiny_core.events import EventType, MutinyEvent
from mutiny_core.genome.models import AttackGenome, AttackMessage
from mutiny_core.policy.models import PolicyEvidence, PolicyHit
from mutiny_core.trace.models import ExecutionTrace, ToolCall, TraceTurn


FAKE_TOKEN = "test-mpr8c-token-not-real-secret"
SECRET_VALUE = "sk-super-secret-mpr8c-value"


POLICY_MIN = """\
version: "1"
target: openai_agents_project
rules:
  - id: refund_limit
    description: Refunds over $200 require approval
    tool: issue_refund
    kind: require_args
    when:
      amount:
        gt: 200
    require:
      approved:
        eq: true
"""

ADAPTER_MIN = '''\
from demo_agent import DemoSupportAgent, InProcessDemoAdapter

def create_adapter():
    return InProcessDemoAdapter(agent=DemoSupportAgent(enforce_refund_policy=False))
'''


def _scaffold(tmp: Path, *, api_url: str = "http://127.0.0.1:8000") -> Path:
    (tmp / ".mutiny").mkdir(parents=True)
    (tmp / ".mutiny" / "adapter.py").write_text(ADAPTER_MIN, encoding="utf-8")
    (tmp / "policy.yaml").write_text(POLICY_MIN, encoding="utf-8")
    (tmp / "mutiny.yaml").write_text(
        yaml.dump(
            {
                "population_size": 2,
                "max_generations": 1,
                "elite_count": 1,
                "max_turns": 2,
                "stop_on_first_violation": True,
                "rng_seed": 0,
                "use_boundary_seeds": True,
                "hosted": {"api_url": api_url, "ui_url": "http://127.0.0.1:3000"},
            }
        ),
        encoding="utf-8",
    )
    return tmp


def _scored(
    cid: str = "cand-1",
    *,
    violated: bool = False,
    api_key: str | None = None,
) -> ScoredCandidate:
    args: dict[str, Any] = {"amount": 500}
    if api_key is not None:
        args["api_key"] = api_key
    genome = AttackGenome(
        id=cid,
        generation=0,
        strategy="seed",
        messages=[AttackMessage(content="please refund")],
        target_rule_ids=["refund_limit"],
    )
    trace = ExecutionTrace(
        candidate_id=cid,
        session_id=f"camp-{cid}",
        turns=[
            TraceTurn(
                user_message="please refund",
                tool_calls=[ToolCall(id="tc1", name="issue_refund", arguments=args)],
                raw={"api_key": api_key or "should-strip"},
            )
        ],
        all_tool_calls=[ToolCall(id="tc1", name="issue_refund", arguments=args)],
        status="violator" if violated else "scored",
        fitness=0.9 if violated else 0.1,
    )
    hits = [
        PolicyHit(
            rule_id="refund_limit",
            violated=violated,
            proximity=1.0 if violated else 0.2,
            evidence=PolicyEvidence(
                rule_id="refund_limit",
                message="hit",
                tool_name="issue_refund",
                arguments=args,
            ),
        )
    ]
    return ScoredCandidate(
        genome=genome,
        trace=trace,
        fitness=0.9 if violated else 0.1,
        violated=violated,
        hits=hits,
        signals={"policy": 1.0},
    )


def _bundle(
    tmp: Path,
    *,
    campaign_id: str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    status: str = "completed",
    violated: bool = False,
    with_regression: bool = False,
    secret_in_trace: bool = False,
) -> LocalRunBundle:
    scored = _scored(
        "cand-1",
        violated=violated,
        api_key=SECRET_VALUE if secret_in_trace else None,
    )
    result = CampaignResult(
        status=status,  # type: ignore[arg-type]
        reason="violation" if violated else "gmax",
        generations_completed=1,
        candidates=[scored],
        best=scored if violated else scored,
        violated=violated,
        events_emitted=3,
    )
    events = [
        MutinyEvent(type=EventType.CAMPAIGN_STARTED, payload={"population_size": 2}),
        MutinyEvent(
            type=EventType.GENERATION_STARTED, payload={"generation": 0, "population": 2}
        ),
        MutinyEvent(
            type=EventType.CANDIDATE_EXECUTING,
            payload={"candidate_id": "cand-1", "generation": 0},
        ),
        MutinyEvent(
            type=EventType.CANDIDATE_SCORED,
            payload={
                "candidate_id": "cand-1",
                "generation": 0,
                "fitness": scored.fitness,
                "violated": violated,
                "trace": {"api_key": SECRET_VALUE},
                "genome": {"id": "cand-1"},
            },
        ),
        MutinyEvent(
            type=EventType.CAMPAIGN_COMPLETED,
            payload={"reason": result.reason, "generations": 1},
        ),
    ]
    if violated:
        events.insert(
            -1,
            MutinyEvent(
                type=EventType.VIOLATION_DETECTED,
                payload={"candidate_id": "cand-1", "fitness": 0.9, "generation": 0},
            ),
        )
    regression_id = None
    regression_path = None
    regression_artifact = None
    minimize_body = None
    if with_regression:
        regression_id = "cli_discovered_violation"
        regression_path = ".mutiny/tests/cli_discovered_violation.json"
        regression_artifact = {
            "version": "1",
            "name": "cli_discovered_violation",
            "target": "openai_agents_project",
            "policy_rule_ids": ["refund_limit"],
            "conversation": ["please refund"],
            "expected": {"must_not_violate": ["refund_limit"]},
            "provenance": {
                "campaign_id": campaign_id,
                "candidate_id": "cand-1",
                "minimized_from_turns": 2,
                "minimized_turn_count": 1,
                "rule_ids": ["refund_limit"],
                "policy_version": "1",
            },
        }
        minimize_body = {
            "candidate_id": "cand-1",
            "original_turn_count": 2,
            "minimized_turn_count": 1,
            "still_reproduces": True,
            "target_rule_ids": ["refund_limit"],
        }
        events.insert(
            -1,
            MutinyEvent(
                type=EventType.REGRESSION_CREATED,
                payload={
                    "campaign_id": campaign_id,
                    "regression_id": regression_id,
                    "candidate_id": "cand-1",
                },
            ),
        )
    return LocalRunBundle(
        campaign_id=campaign_id,
        project_root=tmp,
        config={
            "population_size": 2,
            "max_generations": 1,
            "elite_count": 1,
            "max_turns": 2,
            "stop_on_first_violation": True,
            "rng_seed": 0,
            "use_boundary_seeds": True,
        },
        policy_version="1",
        policy_target="openai_agents_project",
        result=result,
        events=events,
        regression_id=regression_id,
        regression_path=regression_path,
        regression_artifact=regression_artifact,
        minimize_body=minimize_body,
        started_at="2026-09-09T00:00:00Z",
        completed_at="2026-09-09T00:00:05Z",
    )


def test_01_plain_run_remains_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    sync = MagicMock(return_value=0)
    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", sync)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="x",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=0
            ),
        ),
    )
    assert main(["run", "--path", str(tmp_path)]) == 0
    sync.assert_not_called()
    assert "Execution mode: local" in capsys.readouterr().out


def test_02_hosted_executes_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    local_n = {"n": 0}

    def fake_local(*a: Any, **k: Any) -> run_cmd.LocalRunOutcome:
        local_n["n"] += 1
        return run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="camp-local",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=1
            ),
            events=[],
        )

    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda *a, **k: SyncOutcome(ok=True, message="ok"),
    )
    code = main(["run", "--path", str(tmp_path), "--hosted"])
    out = capsys.readouterr().out
    assert code == 0
    assert local_n["n"] == 1
    assert "local + Hosted sync" in out


def test_03_hosted_url_respected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scaffold(tmp_path)
    seen: dict[str, Any] = {}

    def capture(**kwargs: Any) -> int:
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", capture)
    assert (
        main(["run", "--path", str(tmp_path), "--hosted-url", "http://example:9"])
        == 0
    )
    assert seen["api_url"] == "http://example:9"


def test_04_hosted_config_alone_does_not_activate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scaffold(tmp_path)
    sync = MagicMock(return_value=0)
    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", sync)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="x",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=0
            ),
        ),
    )
    assert main(["run", "--path", str(tmp_path)]) == 0
    sync.assert_not_called()


def test_05_explicit_hosted_sync_fail_not_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="camp-x",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=1
            ),
            events=[],
        ),
    )
    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda *a, **k: SyncOutcome(
            ok=False, message="boom", error_code="hosted_unavailable"
        ),
    )
    code = main(["run", "--path", str(tmp_path), "--hosted"])
    err = capsys.readouterr().err
    assert code == SYNC_FAILED_EXIT
    assert "synchronization failed" in err.lower()


def test_06_token_sent_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUTINY_API_TOKEN", f"  {FAKE_TOKEN}  ")
    assert auth_headers_from_env() == {"Authorization": f"Bearer {FAKE_TOKEN}"}


def test_07_missing_token_clear_sync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MUTINY_API_TOKEN", raising=False)
    bundle = _bundle(tmp_path)

    class FakeResp:
        status_code = 401
        text = '{"error":{"code":"unauthorized","message":"authentication required"}}'

        def json(self) -> dict[str, Any]:
            return {
                "error": {"code": "unauthorized", "message": "authentication required"}
            }

    class FakeClient:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def post(self, *a: Any, **k: Any) -> FakeResp:
            return FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)
    out = sync_local_campaign(
        bundle, api_url="http://127.0.0.1:8000", write_pending_on_failure=False
    )
    assert out.ok is False
    assert out.http_status == 401
    assert "MUTINY_API_TOKEN" in out.message or "authentication" in out.message.lower()


def test_08_token_never_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MUTINY_API_TOKEN", FAKE_TOKEN)
    _scaffold(tmp_path)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="camp-tok",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=1
            ),
            events=[],
        ),
    )
    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda *a, **k: SyncOutcome(
            ok=False,
            message="Hosted authentication failed (set a valid MUTINY_API_TOKEN)",
            error_code="unauthorized",
        ),
    )
    main(["run", "--path", str(tmp_path), "--hosted"])
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert FAKE_TOKEN not in blob


def test_09_campaign_payload_matches_schema(tmp_path: Path) -> None:
    body = build_campaign_open_payload(_bundle(tmp_path))
    assert body["schema_version"] == 1
    assert body["execution_mode"] == "local_cli"
    assert body["redaction"]["applied"] is True
    assert body["campaign_id"]
    assert body["local_project_key"].startswith("cli:")
    assert "project_path" not in body
    assert body["attestation"] is True
    assert body["config"]["execution_mode"] == "local_cli"


def test_10_batch_payload_matches_schema(tmp_path: Path) -> None:
    body = build_batch_payload(_bundle(tmp_path, violated=True, secret_in_trace=True))
    assert body["schema_version"] == 1
    assert body["redaction"]["applied"] is True
    assert isinstance(body["events"], list) and body["events"]
    assert isinstance(body["artifacts"], list) and body["artifacts"]
    types = {e["type"] for e in body["events"]}
    assert "candidate.executing" not in types
    assert "campaign.started" in types
    assert "candidate.scored" in types


def test_11_completion_payload_matches_schema(tmp_path: Path) -> None:
    body = build_complete_payload(_bundle(tmp_path, violated=True))
    assert body["schema_version"] == 1
    assert body["status"] == "violation"
    assert body["redaction"]["applied"] is True
    assert body["metrics"]["violated"] is True


def test_12_regression_payload_matches_schema(tmp_path: Path) -> None:
    body = build_regression_payload(_bundle(tmp_path, with_regression=True))
    assert body is not None
    assert body["schema_version"] == 1
    assert body["regression_id"] == "cli_discovered_violation"
    assert body["campaign_id"]
    assert body["artifact"]["version"] == "1"
    assert body["redaction"]["applied"] is True


def test_13_test_run_payload_matches_schema() -> None:
    body = build_test_run_payload(
        test_run_id="tr-1",
        regression_id="reg-1",
        status="PASS",
        duration_ms=12.5,
        policy_version="1",
        evidence=[{"tool": "x", "api_key": SECRET_VALUE}],
    )
    assert body["schema_version"] == 1
    assert body["execution_mode"] == "local_cli"
    assert body["status"] == "PASS"
    assert body["evidence"][0]["api_key"] == "[REDACTED]"
    assert body["redaction"]["applied"] is True


def test_14_secrets_redacted_before_http(tmp_path: Path) -> None:
    body = build_batch_payload(_bundle(tmp_path, violated=True, secret_in_trace=True))
    blob = json.dumps(body)
    assert SECRET_VALUE not in blob
    assert "[REDACTED]" in blob
    for art in body["artifacts"]:
        if art["kind"] == "trace":
            for turn in art["body"].get("turns") or []:
                assert "raw" not in turn or turn.get("raw") is None


def test_15_redaction_disabled_refuses_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_DISABLE_SECRET_REDACTION", "1")
    with pytest.raises(RedactionDisabledError):
        ensure_redaction_allowed_for_upload()
    out = sync_local_campaign(
        _bundle(tmp_path),
        api_url="http://127.0.0.1:8000",
        write_pending_on_failure=False,
    )
    assert out.ok is False
    assert out.error_code == "redaction_disabled"


def test_16_project_paths_not_execution_instructions(tmp_path: Path) -> None:
    open_body = build_campaign_open_payload(_bundle(tmp_path))
    assert "project_path" not in open_body
    assert open_body["project_label"] == tmp_path.name
    key = local_project_key(tmp_path)
    assert not Path(key).exists()
    assert str(tmp_path.resolve()) not in key


def test_17_customer_python_never_uploaded(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    src = (tmp_path / ".mutiny" / "adapter.py").read_text(encoding="utf-8")
    open_b = build_campaign_open_payload(_bundle(tmp_path))
    batch = build_batch_payload(_bundle(tmp_path, with_regression=True))
    blob = json.dumps({"open": open_b, "batch": batch})
    assert "create_adapter" not in blob
    assert "DemoSupportAgent" not in blob
    assert src[:40] not in blob


def test_18_hosted_execution_path_not_invoked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--hosted`` must not call CampaignSupervisor / start / old create path."""
    _scaffold(tmp_path)
    posts: list[str] = []

    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="camp-no-exec",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=1
            ),
            events=[],
        ),
    )

    class FakeClient:
        def open_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
            posts.append("/api/ingest/v1/campaigns")
            assert payload.get("execution_mode") == "local_cli"
            return {"ok": True}

        def post_batch(self, cid: str, payload: dict[str, Any]) -> dict[str, Any]:
            posts.append(f"/api/ingest/v1/campaigns/{cid}/batch")
            return {"ok": True}

        def complete_campaign(self, cid: str, payload: dict[str, Any]) -> dict[str, Any]:
            posts.append(f"/api/ingest/v1/campaigns/{cid}/complete")
            return {"ok": True}

        def post_regression(self, payload: dict[str, Any]) -> dict[str, Any]:
            posts.append("/api/ingest/v1/regressions")
            return {"ok": True}

    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda bundle, **kw: sync_local_campaign(
            bundle,
            api_url=kw["api_url"],
            ui_url=kw.get("ui_url"),
            client=FakeClient(),  # type: ignore[arg-type]
            write_pending_on_failure=False,
        ),
    )

    code = run_cmd._run_local_with_hosted_sync(
        root=tmp_path,
        config={"population_size": 2},
        policy=MagicMock(version="1", target="t"),
        api_url="http://127.0.0.1:8000",
        ui_url="http://127.0.0.1:3000",
    )
    assert code == 0
    assert posts
    assert all("/api/ingest/" in p for p in posts)
    assert not any("/start" in p for p in posts)
    src = Path(hosted_sync.__file__).read_text(encoding="utf-8")
    for name in (
        "CampaignSupervisor",
        "load_adapter_factory",
        "exec_module",
    ):
        assert f"import {name}" not in src
        assert f"{name}(" not in src


def test_19_local_success_hosted_success(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    calls: list[str] = []

    class OkClient:
        def open_campaign(self, p: dict[str, Any]) -> dict[str, Any]:
            calls.append("open")
            return {}

        def post_batch(self, cid: str, p: dict[str, Any]) -> dict[str, Any]:
            calls.append("batch")
            return {}

        def complete_campaign(self, cid: str, p: dict[str, Any]) -> dict[str, Any]:
            calls.append("complete")
            assert p["status"] == "completed"
            return {}

        def post_regression(self, p: dict[str, Any]) -> dict[str, Any]:
            calls.append("regression")
            return {}

    out = sync_local_campaign(
        bundle,
        api_url="http://127.0.0.1:8000",
        client=OkClient(),  # type: ignore[arg-type]
        write_pending_on_failure=False,
    )
    assert out.ok is True
    assert calls == ["open", "batch", "complete"]


def test_20_local_success_hosted_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="camp-unavail",
            result=CampaignResult(
                status="completed", reason="gmax", generations_completed=1
            ),
            events=[],
        ),
    )
    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda *a, **k: SyncOutcome(
            ok=False, message="Hosted unreachable", error_code="hosted_unavailable"
        ),
    )
    code = run_cmd._run_local_with_hosted_sync(
        root=tmp_path,
        config={},
        policy=MagicMock(version="1", target="t"),
        api_url="http://127.0.0.1:9",
        ui_url="http://127.0.0.1:3000",
    )
    assert code == SYNC_FAILED_EXIT
    assert "authoritative" in capsys.readouterr().err.lower()


def test_21_local_failure_still_attempts_hosted_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scaffold(tmp_path)
    sync_called = {"n": 0}

    def fake_local(*a: Any, **k: Any) -> run_cmd.LocalRunOutcome:
        return run_cmd.LocalRunOutcome(
            exit_code=1,
            campaign_id="camp-fail",
            result=CampaignResult(
                status="error", reason="tools_not_observable", generations_completed=0
            ),
            events=[
                MutinyEvent(
                    type=EventType.CAMPAIGN_ERROR, payload={"error": "no tools"}
                )
            ],
        )

    def fake_sync(bundle: LocalRunBundle, **kw: Any) -> SyncOutcome:
        sync_called["n"] += 1
        assert terminal_status(bundle.result) == "failed"
        return SyncOutcome(ok=True, message="reported")

    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setattr(run_cmd, "sync_local_campaign", fake_sync)
    code = run_cmd._run_local_with_hosted_sync(
        root=tmp_path,
        config={},
        policy=MagicMock(version="1", target="t"),
        api_url="http://127.0.0.1:8000",
        ui_url="http://127.0.0.1:3000",
    )
    assert sync_called["n"] == 1
    assert code == 1


def test_22_duplicate_sync_same_campaign_identity(tmp_path: Path) -> None:
    b1 = _bundle(tmp_path, campaign_id="same-camp-id")
    b2 = _bundle(tmp_path, campaign_id="same-camp-id")
    e1 = build_ingest_events(b1.campaign_id, b1.events)
    e2 = build_ingest_events(b2.campaign_id, b2.events)
    assert [e["event_id"] for e in e1] == [e["event_id"] for e in e2]
    assert build_campaign_open_payload(b1)["campaign_id"] == "same-camp-id"
    assert build_campaign_open_payload(b2)["campaign_id"] == "same-camp-id"


def test_23_hosted_409_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResp:
        status_code = 409
        text = '{"error":{"code":"campaign_conflict","message":"conflict"}}'

        def json(self) -> dict[str, Any]:
            return {"error": {"code": "campaign_conflict", "message": "conflict"}}

    class FakeClient:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def post(self, *a: Any, **k: Any) -> FakeResp:
            return FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = HostedIngestClient("http://127.0.0.1:8000")
    with pytest.raises(HostedSyncError) as ei:
        client.open_campaign({"schema_version": 1, "campaign_id": "x"})
    assert ei.value.http_status == 409
    assert "conflict" in str(ei.value).lower()


def test_24_hosted_413_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResp:
        status_code = 413
        text = '{"error":{"code":"payload_too_large","message":"too big"}}'

        def json(self) -> dict[str, Any]:
            return {"error": {"code": "payload_too_large", "message": "too big"}}

    class FakeClient:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def post(self, *a: Any, **k: Any) -> FakeResp:
            return FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = HostedIngestClient("http://127.0.0.1:8000")
    with pytest.raises(HostedSyncError) as ei:
        client.post_batch("c1", {"schema_version": 1})
    assert ei.value.http_status == 413
    assert ei.value.error_code == "payload_too_large"


def test_25_uploaded_event_ids_stable(tmp_path: Path) -> None:
    b = _bundle(tmp_path, campaign_id="stable-camp")
    a = build_ingest_events(b.campaign_id, b.events)
    b_again = build_ingest_events(b.campaign_id, b.events)
    assert a and a == b_again
    assert all(re.match(r"^[0-9a-f-]{36}$", e["event_id"]) for e in a)


def test_26_regression_ids_stable(tmp_path: Path) -> None:
    b = _bundle(tmp_path, with_regression=True, campaign_id="reg-camp")
    p1 = build_regression_payload(b)
    p2 = build_regression_payload(b)
    assert p1 is not None and p2 is not None
    assert p1["regression_id"] == p2["regression_id"] == "cli_discovered_violation"


def test_27_trace_candidate_relationships_intact(tmp_path: Path) -> None:
    body = build_batch_payload(_bundle(tmp_path, violated=True))
    cands = [a for a in body["artifacts"] if a["kind"] == "candidate"]
    traces = [a for a in body["artifacts"] if a["kind"] == "trace"]
    assert cands and traces
    assert cands[0]["id"] == traces[0]["id"] == traces[0]["candidate_id"]
    assert cands[0]["campaign_id"] == body["campaign_id"]


def test_28_completion_status_matches_local_result(tmp_path: Path) -> None:
    assert (
        build_complete_payload(_bundle(tmp_path, violated=True))["status"]
        == "violation"
    )
    assert (
        build_complete_payload(_bundle(tmp_path, status="completed"))["status"]
        == "completed"
    )
    assert (
        build_complete_payload(_bundle(tmp_path, status="error"))["status"] == "failed"
    )


def test_29_pending_file_written_on_sync_failure(tmp_path: Path) -> None:
    class Boom:
        def open_campaign(self, *a: Any, **k: Any) -> dict[str, Any]:
            raise HostedSyncError("down", error_code="hosted_unavailable")

    out = sync_local_campaign(
        _bundle(tmp_path, campaign_id="pending-camp"),
        api_url="http://127.0.0.1:8000",
        client=Boom(),  # type: ignore[arg-type]
        write_pending_on_failure=True,
    )
    assert out.ok is False
    assert out.pending_path is not None
    assert out.pending_path.is_file()
    doc = json.loads(out.pending_path.read_text(encoding="utf-8"))
    assert doc["kind"] == "hosted_pending_sync"
    assert doc["campaign_id"] == "pending-camp"
    assert doc["payloads"]["open"]["redaction"]["applied"] is True


def test_30_sync_module_has_no_exec_gadgets() -> None:
    src = Path(hosted_sync.__file__).read_text(encoding="utf-8")
    # No imports / calls that would execute customer code on Hosted.
    for needle in (
        "from mutiny_api",
        "import pickle",
        "shell=True",
        "load_adapter_factory(",
        "exec_module(",
        "CampaignSupervisor(",
        "eval(",
    ):
        assert needle not in src
