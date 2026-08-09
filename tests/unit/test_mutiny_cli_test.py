"""Milestone D: ``mutiny test`` CLI — discover, replay, exit codes, report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mutiny_cli.main import main
from mutiny_cli.test_cmd import discover_regressions, run_tests

ROOT = Path(__file__).resolve().parents[2]
DEMO_POLICY = ROOT / "examples" / "policies" / "demo_support.json"
REGRESSION = ROOT / "examples" / "regressions" / "refund_limit_m5.json"

ADAPTER_SRC = '''\
"""Test adapter — InProcessDemoAdapter for CLI regression replay."""
from demo_agent import DemoSupportAgent, InProcessDemoAdapter

def create_adapter(*, enforce_refund_policy: bool = False):
    return InProcessDemoAdapter(
        agent=DemoSupportAgent(enforce_refund_policy=enforce_refund_policy)
    )
'''


def _scaffold(tmp: Path, *, fixed: bool = False) -> Path:
    (tmp / ".mutiny" / "tests").mkdir(parents=True)
    shutil.copy(DEMO_POLICY, tmp / "policy.json")
    adapter = ADAPTER_SRC
    if fixed:
        adapter = adapter.replace(
            "enforce_refund_policy=enforce_refund_policy",
            "enforce_refund_policy=True",
        )
    (tmp / ".mutiny" / "adapter.py").write_text(adapter, encoding="utf-8")
    shutil.copy(REGRESSION, tmp / ".mutiny" / "tests" / "refund_limit.json")
    return tmp


def test_discover_regressions(tmp_path: Path):
    _scaffold(tmp_path)
    found = discover_regressions(tmp_path)
    assert len(found) == 1
    assert found[0]["id"] == "refund_limit"
    assert found[0]["artifact"].name == "refund_limit_over_200_unapproved"


def test_mutiny_test_vulnerable_fails(tmp_path: Path):
    _scaffold(tmp_path, fixed=False)
    code = run_tests(project_root=tmp_path, json_out=False)
    assert code == 1
    report = json.loads((tmp_path / ".mutiny" / "test-report.json").read_text())
    assert report["failed"] == 1
    assert report["passed"] == 0
    assert report["results"][0]["status"] == "FAIL"
    assert "refund_limit" in report["results"][0]["violated_rule_ids"]
    assert report["policy_version"] == "1"


def test_mutiny_test_fixed_passes(tmp_path: Path):
    _scaffold(tmp_path, fixed=True)
    code = run_tests(project_root=tmp_path)
    assert code == 0
    report = json.loads((tmp_path / ".mutiny" / "test-report.json").read_text())
    assert report["passed"] == 1
    assert report["failed"] == 0
    assert report["results"][0]["status"] == "PASS"


def test_mutiny_test_by_id_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _scaffold(tmp_path, fixed=True)
    code = run_tests(
        project_root=tmp_path,
        regression_id="refund_limit",
        json_out=True,
    )
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["passed"] == 1
    assert data["results"][0]["id"] == "refund_limit"


def test_mutiny_test_failed_filter(tmp_path: Path):
    _scaffold(tmp_path, fixed=False)
    assert run_tests(project_root=tmp_path) == 1
    # Switch to fixed agent but --failed should still select the prior FAIL case
    (tmp_path / ".mutiny" / "adapter.py").write_text(
        ADAPTER_SRC.replace(
            "enforce_refund_policy=enforce_refund_policy",
            "enforce_refund_policy=True",
        ),
        encoding="utf-8",
    )
    code = run_tests(project_root=tmp_path, failed_only=True)
    assert code == 0


def test_mutiny_test_no_regressions_exit_zero(tmp_path: Path):
    (tmp_path / ".mutiny").mkdir()
    shutil.copy(DEMO_POLICY, tmp_path / "policy.json")
    (tmp_path / ".mutiny" / "adapter.py").write_text(ADAPTER_SRC, encoding="utf-8")
    assert run_tests(project_root=tmp_path) == 0


def test_mutiny_test_unknown_id(tmp_path: Path):
    _scaffold(tmp_path, fixed=True)
    assert run_tests(project_root=tmp_path, regression_id="does_not_exist") == 2


def test_main_test_subcommand(tmp_path: Path):
    _scaffold(tmp_path, fixed=True)
    assert main(["test", "--path", str(tmp_path)]) == 0
