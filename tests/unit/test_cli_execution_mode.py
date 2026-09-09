"""M-PR2: CLI execution-mode contract — local default, explicit Hosted."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from mutiny_cli.init_cmd import run_init
from mutiny_cli.main import main
from mutiny_cli import run_cmd
from mutiny_cli.test_cmd import run_tests


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


# —— Test A: default is local ——


def test_a_default_run_is_local_even_with_hosted_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    hosted_calls: list[dict[str, Any]] = []
    local_calls: list[Path] = []

    def fake_hosted(**kwargs: Any) -> int | None:
        hosted_calls.append(kwargs)
        return 0

    def fake_local(root: Path, config: dict[str, Any], policy: Any) -> int:
        local_calls.append(root)
        return 0

    monkeypatch.setattr(run_cmd, "_run_via_hosted", fake_hosted)
    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setenv("MUTINY_API_URL", "http://evil.example:9999")

    code = main(["run", "--path", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 0
    assert hosted_calls == []
    assert len(local_calls) == 1
    assert local_calls[0] == tmp_path.resolve()
    assert "Execution mode: local" in out


# —— Test B: explicit Hosted uses Hosted ——


def test_b_hosted_flag_selects_hosted_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    hosted_calls: list[dict[str, Any]] = []
    local_calls: list[Path] = []

    def fake_hosted(**kwargs: Any) -> int:
        hosted_calls.append(kwargs)
        return 0

    def fake_local(root: Path, config: dict[str, Any], policy: Any) -> int:
        local_calls.append(root)
        return 0

    monkeypatch.setattr(run_cmd, "_run_via_hosted", fake_hosted)
    monkeypatch.setattr(run_cmd, "_run_local", fake_local)

    code = main(["run", "--path", str(tmp_path), "--hosted"])
    out = capsys.readouterr().out

    assert code == 0
    assert len(hosted_calls) == 1
    assert hosted_calls[0]["api_url"] == "http://127.0.0.1:8000"
    assert local_calls == []
    assert "Execution mode: hosted" in out


def test_b_hosted_url_flag_also_selects_hosted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI ``--hosted-url`` is explicit Hosted intent (URL override)."""
    _scaffold(tmp_path)
    hosted_calls: list[dict[str, Any]] = []

    def fake_hosted(**kwargs: Any) -> int:
        hosted_calls.append(kwargs)
        return 0

    monkeypatch.setattr(run_cmd, "_run_via_hosted", fake_hosted)
    monkeypatch.setattr(run_cmd, "_run_local", lambda *a, **k: 99)

    code = main(
        ["run", "--path", str(tmp_path), "--hosted-url", "http://127.0.0.1:18000"]
    )
    assert code == 0
    assert len(hosted_calls) == 1
    assert hosted_calls[0]["api_url"] == "http://127.0.0.1:18000"


# —— Test C: no accidental fallback ——


def test_c_explicit_hosted_unavailable_does_not_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    local_calls: list[Path] = []

    def fake_hosted(**kwargs: Any) -> int:
        print("error: Hosted API unreachable at http://127.0.0.1:8000", file=__import__("sys").stderr)
        return 1

    monkeypatch.setattr(run_cmd, "_run_via_hosted", fake_hosted)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda root, config, policy: local_calls.append(root) or 0,
    )

    code = main(["run", "--path", str(tmp_path), "--hosted"])
    err = capsys.readouterr().err

    assert code == 1
    assert local_calls == []
    assert "Hosted" in err or code == 1


def test_c_run_via_hosted_explicit_no_silent_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When Hosted is explicit, connectivity failures must return an error code."""
    _scaffold(tmp_path)

    class BoomClient:
        def __init__(self, *a: Any, **k: Any) -> None:
            raise ConnectionError("refused")

        def __enter__(self) -> BoomClient:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    fake_httpx = MagicMock()
    fake_httpx.Client = BoomClient
    monkeypatch.setitem(__import__("sys").modules, "httpx", fake_httpx)

    code = run_cmd._run_via_hosted(
        config={"population_size": 2},
        hosted_cfg={"api_url": "http://127.0.0.1:8000"},
        api_url="http://127.0.0.1:8000",
        ui_url="http://127.0.0.1:3000",
        project_root=tmp_path,
        explicit=True,
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "fallback" not in err.lower()
    assert "Hosted" in err or "unreachable" in err.lower() or "refused" in err.lower()


# —— Test D: local works without Hosted ——


def test_d_local_run_without_hosted_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path, api_url="")
    cfg = yaml.safe_load((tmp_path / "mutiny.yaml").read_text())
    cfg["hosted"] = {}
    (tmp_path / "mutiny.yaml").write_text(yaml.dump(cfg), encoding="utf-8")

    local_calls: list[Path] = []
    monkeypatch.setattr(run_cmd, "_run_via_hosted", lambda **k: (_ for _ in ()).throw(AssertionError("hosted")))
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda root, config, policy: local_calls.append(root) or 0,
    )

    code = main(["run", "--path", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert len(local_calls) == 1
    assert "Execution mode: local" in out


# —— Test E: mutiny test stays local ——


def test_e_mutiny_test_has_no_hosted_mode() -> None:
    """``mutiny test`` must not grow a Hosted path merely for consistency."""
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
    # empty suite → exit 0 locally
    code = run_tests(project_root=tmp_path, write_report=False)
    assert code == 0


# —— Test F: compatibility ——


def test_f_no_hosted_remains_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    local_calls: list[Path] = []
    monkeypatch.setattr(run_cmd, "_run_via_hosted", lambda **k: 0)
    monkeypatch.setattr(
        run_cmd,
        "_run_local",
        lambda root, config, policy: local_calls.append(root) or 0,
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
    # Default path is local; hint should not require --no-hosted
    assert "mutiny run --no-hosted" not in out


def test_f_reachable_api_does_not_auto_select_hosted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if Hosted would succeed, default must not call it."""
    _scaffold(tmp_path)
    called = {"hosted": False}

    def would_succeed(**kwargs: Any) -> int:
        called["hosted"] = True
        return 0

    monkeypatch.setattr(run_cmd, "_run_via_hosted", would_succeed)
    monkeypatch.setattr(run_cmd, "_run_local", lambda *a, **k: 0)
    assert main(["run", "--path", str(tmp_path)]) == 0
    assert called["hosted"] is False
