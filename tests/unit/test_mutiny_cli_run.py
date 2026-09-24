"""Unit tests for ``mutiny run`` CLI — crash prevention, validation, and error handling (Issue #57)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from mutiny_cli.init_cmd import run_init
from mutiny_cli.main import main

ROOT = Path(__file__).resolve().parents[2]
DEMO_POLICY = ROOT / "examples" / "policies" / "demo_support.json"

ADAPTER_MIN = '''\
from demo_agent import DemoSupportAgent, InProcessDemoAdapter

def create_adapter():
    return InProcessDemoAdapter(agent=DemoSupportAgent(enforce_refund_policy=False))
'''

ADAPTER_CRASHING = '''\
from demo_agent import InProcessDemoAdapter

class CrashingAdapter(InProcessDemoAdapter):
    def step(self, session_id, user_message):
        raise RuntimeError("simulated OpenAI SDK outage")

def create_adapter():
    return CrashingAdapter()
'''


def _scaffold(tmp: Path) -> Path:
    (tmp / ".mutiny").mkdir(parents=True, exist_ok=True)
    shutil.copy(DEMO_POLICY, tmp / "policy.json")
    (tmp / ".mutiny" / "adapter.py").write_text(ADAPTER_MIN, encoding="utf-8")
    (tmp / "mutiny.yaml").write_text(
        yaml.dump(
            {
                "population_size": 4,
                "max_generations": 2,
                "elite_count": 1,
            }
        ),
        encoding="utf-8",
    )
    return tmp


def test_empty_dir_mutiny_run_exits_2_with_clean_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["run", "--path", str(tmp_path)])
    assert code == 2
    captured = capsys.readouterr()
    assert "mutiny init" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_empty_dir_mutiny_test_exits_2_with_clean_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["test", "--path", str(tmp_path)])
    assert code == 2
    captured = capsys.readouterr()
    assert "mutiny init" in captured.err
    assert "invalid project policy" not in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_init_then_run_in_empty_project_exits_2_with_adapter_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    monkeypatch.setattr(
        sys,
        "path",
        [p for p in sys.path if "openai_support_agent" not in p],
    )
    monkeypatch.delitem(sys.modules, "agent", raising=False)

    assert run_init(project_root=tmp_path) == 0
    capsys.readouterr()

    code = main(["run", "--path", str(tmp_path)])
    assert code == 2
    captured = capsys.readouterr()
    assert "adapter" in captured.err.lower()
    assert "init" in captured.err.lower()
    assert "Traceback" not in captured.err
    assert "ModuleNotFoundError" not in captured.err or "error: could not load adapter" in captured.err


def test_invalid_population_size_exits_2_before_search_banner(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    (tmp_path / "mutiny.yaml").write_text(
        yaml.dump({"population_size": 100}), encoding="utf-8"
    )

    code = main(["run", "--path", str(tmp_path)])
    assert code == 2
    captured = capsys.readouterr()
    assert "search:  N=" not in captured.out
    assert "invalid mutiny.yaml" in captured.err
    assert "Traceback" not in captured.err


def test_malformed_yaml_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    (tmp_path / "mutiny.yaml").write_text(": bad yaml ::", encoding="utf-8")

    code = main(["run", "--path", str(tmp_path)])
    assert code == 2
    captured = capsys.readouterr()
    assert "invalid mutiny.yaml" in captured.err
    assert "Traceback" not in captured.err


def test_missing_policy_with_existing_mutiny_yaml_exits_2_with_init_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "mutiny.yaml").write_text("population_size: 4\n", encoding="utf-8")

    code_run = main(["run", "--path", str(tmp_path)])
    assert code_run == 2
    captured_run = capsys.readouterr()
    assert "mutiny init" in captured_run.err
    assert "invalid project policy" not in captured_run.err
    assert "Traceback" not in captured_run.err

    code_test = main(["test", "--path", str(tmp_path)])
    assert code_test == 2
    captured_test = capsys.readouterr()
    assert "mutiny init" in captured_test.err
    assert "invalid project policy" not in captured_test.err
    assert "Traceback" not in captured_test.err


def test_adapter_runtime_error_during_run_exits_1_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    (tmp_path / ".mutiny" / "adapter.py").write_text(ADAPTER_CRASHING, encoding="utf-8")

    code = main(["run", "--path", str(tmp_path)])
    assert code == 1
    captured = capsys.readouterr()
    assert "status=error" in captured.out
    assert "simulated OpenAI SDK outage" in captured.out
    assert "Traceback" not in captured.err
