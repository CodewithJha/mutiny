"""M-PR1: Hosted kill-switch — refuse arbitrary customer adapter exec by default."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_api.supervisor import (
    PRODUCT_TARGET,
    HostedProjectExecDisabled,
    _make_adapter,
    hosted_project_exec_allowed,
    validate_campaign_config,
)
from mutiny_openai_agents.loader import load_adapter_factory

MARKER_NAME = "MUTINY_KILL_SWITCH_EXECUTED"


def _malicious_project(tmp_path: Path) -> Path:
    """Project whose adapter leaves an unmistakable side effect if imported."""
    mutiny = tmp_path / ".mutiny"
    mutiny.mkdir()
    marker = tmp_path / MARKER_NAME
    (mutiny / "adapter.py").write_text(
        f"""\
from pathlib import Path
Path({str(marker)!r}).write_text("executed", encoding="utf-8")

def create_adapter():
    raise RuntimeError("adapter factory must not run under kill-switch")
""",
        encoding="utf-8",
    )
    (tmp_path / "policy.yaml").write_text(
        "version: '1'\ntarget: kill_switch_probe\nrules: []\n",
        encoding="utf-8",
    )
    return tmp_path


def test_hosted_project_exec_denied_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test A (unit): validate / _make_adapter must not exec customer adapter."""
    monkeypatch.delenv("MUTINY_ALLOW_PROJECT_EXEC", raising=False)
    assert hosted_project_exec_allowed() is False

    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME
    assert not marker.exists()

    with pytest.raises(HostedProjectExecDisabled, match="disabled"):
        validate_campaign_config(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(project),
            }
        )
    assert not marker.exists(), "adapter.py must not have been executed"

    with pytest.raises(HostedProjectExecDisabled, match="disabled"):
        _make_adapter(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(project),
            }
        )
    assert not marker.exists(), "adapter.py must not have been executed"


def test_opt_in_allows_hosted_project_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opt-in flag restores Hosted loader for single-operator localhost only."""
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    assert hosted_project_exec_allowed() is True

    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME

    # validate_campaign_config imports adapter via load_adapter_factory (side effect)
    # but does not call create_adapter().
    cfg = validate_campaign_config(
        {
            "target": PRODUCT_TARGET,
            "project_path": str(project),
        }
    )
    assert cfg["project_path"] == str(project.resolve())
    assert marker.exists(), "opt-in must reach exec_module"


def test_local_cli_loader_unaffected_by_kill_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test D: CLI/local load_adapter_factory still executes customer adapters."""
    monkeypatch.delenv("MUTINY_ALLOW_PROJECT_EXEC", raising=False)
    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME

    factory = load_adapter_factory(project)
    assert marker.exists(), "CLI loader must still exec_module adapter.py"
    with pytest.raises(RuntimeError, match="adapter factory must not run"):
        factory()


def test_harness_target_still_builds_without_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test C (unit): trusted in_process_demo does not need the opt-in flag."""
    monkeypatch.delenv("MUTINY_ALLOW_PROJECT_EXEC", raising=False)
    cfg = validate_campaign_config({"target": "in_process_demo"})
    adapter = _make_adapter(cfg)
    assert adapter.__class__.__name__ == "InProcessDemoAdapter"
