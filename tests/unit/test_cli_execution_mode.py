"""M-PR2 + M-PR8C: CLI execution-mode — local default; ``--hosted`` = local + sync."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from mutiny_cli.init_cmd import run_init
from mutiny_cli.main import main
from mutiny_cli import run_cmd
from mutiny_cli.hosted_sync import SYNC_FAILED_EXIT, LocalRunBundle, SyncOutcome
from mutiny_cli.test_cmd import run_tests
from mutiny_core.campaign.engine import CampaignResult


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
"""Minimal adapter for CLI execution-mode unit tests."""

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
                "hosted": {
                    "api_url": api_url,
                    "ui_url": "http://127.0.0.1:3000",
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp


def _ok_outcome(root: Path) -> run_cmd.LocalRunOutcome:
    result = CampaignResult(
        status="completed",
        reason="gmax",
        generations_completed=1,
        candidates=[],
        best=None,
        violated=False,
        events_emitted=0,
    )
    return run_cmd.LocalRunOutcome(
        exit_code=0,
        campaign_id="11111111-1111-1111-1111-111111111111",
        result=result,
        events=[],
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )


# —— Test A: default is local ——


def test_a_default_run_is_local_even_with_hosted_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    sync_calls: list[Any] = []
    local_calls: list[Path] = []

    def fake_sync(**kwargs: Any) -> int:
        sync_calls.append(kwargs)
        return 0

    def fake_local(
        root: Path, config: dict[str, Any], policy: Any, **kwargs: Any
    ) -> run_cmd.LocalRunOutcome:
        local_calls.append(root)
        return _ok_outcome(root)

    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", fake_sync)
    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setenv("MUTINY_API_URL", "http://evil.example:9999")

    code = main(["run", "--path", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 0
    assert sync_calls == []
    assert len(local_calls) == 1
    assert local_calls[0] == tmp_path.resolve()
    assert "Execution mode: local" in out


# —— Test B: explicit Hosted uses local + sync ——


def test_b_hosted_flag_selects_local_plus_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    sync_calls: list[dict[str, Any]] = []

    def fake_sync(**kwargs: Any) -> int:
        sync_calls.append(kwargs)
        return 0

    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", fake_sync)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("plain local")),
    )

    code = main(["run", "--path", str(tmp_path), "--hosted"])
    out = capsys.readouterr().out

    assert code == 0
    assert len(sync_calls) == 1
    assert sync_calls[0]["api_url"] == "http://127.0.0.1:8000"
    assert "Execution mode: local + Hosted sync" in out


def test_b_hosted_url_flag_also_selects_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI ``--hosted-url`` is explicit Hosted sync intent (URL override)."""
    _scaffold(tmp_path)
    sync_calls: list[dict[str, Any]] = []

    def fake_sync(**kwargs: Any) -> int:
        sync_calls.append(kwargs)
        return 0

    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", fake_sync)

    code = main(
        ["run", "--path", str(tmp_path), "--hosted-url", "http://127.0.0.1:18000"]
    )
    assert code == 0
    assert len(sync_calls) == 1
    assert sync_calls[0]["api_url"] == "http://127.0.0.1:18000"


# —— Test C: no silent fallback from --hosted ——


def test_c_explicit_hosted_sync_fail_does_not_pretend_local_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Local still runs; sync failure is visible (exit 3), not silent local-only."""
    _scaffold(tmp_path)

    def fake_local(
        root: Path, config: dict[str, Any], policy: Any, **kwargs: Any
    ) -> run_cmd.LocalRunOutcome:
        return _ok_outcome(root)

    def fake_sync_fail(bundle: LocalRunBundle, **kwargs: Any) -> SyncOutcome:
        return SyncOutcome(ok=False, message="Hosted unreachable", error_code="hosted_unavailable")

    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setattr(run_cmd, "sync_local_campaign", fake_sync_fail)

    code = main(["run", "--path", str(tmp_path), "--hosted"])
    err = capsys.readouterr().err

    assert code == SYNC_FAILED_EXIT
    assert "synchronization failed" in err.lower() or "Hosted" in err


def test_c_hosted_unavailable_still_runs_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    local_called = {"n": 0}

    def fake_local(
        root: Path, config: dict[str, Any], policy: Any, **kwargs: Any
    ) -> run_cmd.LocalRunOutcome:
        local_called["n"] += 1
        return _ok_outcome(root)

    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda *a, **k: SyncOutcome(ok=False, message="refused", error_code="hosted_unavailable"),
    )

    code = run_cmd._run_local_with_hosted_sync(
        root=tmp_path,
        config={"population_size": 2},
        policy=MagicMock(version="1", target="t"),
        api_url="http://127.0.0.1:8000",
        ui_url="http://127.0.0.1:3000",
    )
    assert local_called["n"] == 1
    assert code == SYNC_FAILED_EXIT
    err = capsys.readouterr().err
    assert "authoritative" in err.lower() or "synchronization failed" in err.lower()


# —— Test D: local works without Hosted ——


def test_d_local_run_without_hosted_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path, api_url="")
    cfg = yaml.safe_load((tmp_path / "mutiny.yaml").read_text())
    cfg["hosted"] = {}
    (tmp_path / "mutiny.yaml").write_text(yaml.dump(cfg), encoding="utf-8")

    local_calls: list[Path] = []
    monkeypatch.setattr(
        run_cmd,
        "_run_local_with_hosted_sync",
        lambda **k: (_ for _ in ()).throw(AssertionError("hosted")),
    )
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda root, config, policy, **kw: (
            local_calls.append(root) or _ok_outcome(root)
        ),
    )

    code = main(["run", "--path", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert len(local_calls) == 1
    assert "Execution mode: local" in out


# —— Test E: mutiny test stays local (no --hosted in M-PR8C) ——


def test_e_mutiny_test_has_no_hosted_mode() -> None:
    """``mutiny test --hosted`` deferred; help must not advertise it yet."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            main(["test", "--help"])
        except SystemExit as exc:
            assert exc.code == 0
    text = buf.getvalue()
    assert "--hosted" not in text
    assert "--no-hosted" not in text


def test_e_mutiny_test_runs_local_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke: run_tests still loads local adapter (no Hosted client)."""
    _scaffold(tmp_path)
    (tmp_path / ".mutiny" / "tests").mkdir(parents=True, exist_ok=True)
    code = run_tests(project_root=tmp_path, write_report=False)
    assert code == 0


# —— Test F: compatibility ——


def test_f_no_hosted_remains_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    local_calls: list[Path] = []
    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", lambda **k: 0)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda root, config, policy, **kw: (
            local_calls.append(root) or _ok_outcome(root)
        ),
    )
    code = main(["run", "--path", str(tmp_path), "--no-hosted"])
    out = capsys.readouterr().out
    assert code == 0
    assert len(local_calls) == 1
    assert "Execution mode: local" in out


def test_f_hosted_and_no_hosted_conflict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    code = main(["run", "--path", str(tmp_path), "--hosted", "--no-hosted"])
    err = capsys.readouterr().err
    assert code == 2
    assert "conflict" in err.lower() or "exclusive" in err.lower() or "--no-hosted" in err


def test_f_init_hint_prefers_plain_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_init(project_root=tmp_path) == 0
    out = capsys.readouterr().out
    assert "mutiny run" in out
    assert "mutiny run --no-hosted" not in out


def test_f_reachable_api_does_not_auto_select_hosted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if Hosted sync would succeed, default must not call it."""
    _scaffold(tmp_path)
    called = {"sync": False}

    def would_succeed(**kwargs: Any) -> int:
        called["sync"] = True
        return 0

    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", would_succeed)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda *a, **k: _ok_outcome(tmp_path),
    )
    assert main(["run", "--path", str(tmp_path)]) == 0
    assert called["sync"] is False
