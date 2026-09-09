"""M-PR8E: Hosted permanently refuses customer adapter exec (was M-PR1 kill-switch)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mutiny_api.supervisor import (
    PRODUCT_TARGET,
    HostedCustomerExecutionRemoved,
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
    raise RuntimeError("adapter factory must not run under M-PR8E")
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
    """validate / _make_adapter must not exec customer adapter."""
    monkeypatch.delenv("MUTINY_ALLOW_PROJECT_EXEC", raising=False)
    assert hosted_project_exec_allowed() is False

    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME
    assert not marker.exists()

    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        validate_campaign_config(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(project),
            }
        )
    assert not marker.exists(), "adapter.py must not have been executed"

    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        _make_adapter(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(project),
            }
        )
    assert not marker.exists(), "adapter.py must not have been executed"


def test_opt_in_cannot_restore_hosted_project_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTINY_ALLOW_PROJECT_EXEC=1 must NOT restore Hosted customer exec (M-PR8E)."""
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    assert hosted_project_exec_allowed() is False

    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME

    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        validate_campaign_config(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(project),
            }
        )
    assert not marker.exists(), "opt-in must not reach exec_module"

    with pytest.raises(HostedCustomerExecutionRemoved):
        _make_adapter(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(project),
            }
        )
    assert not marker.exists()


def test_allow_env_truthy_variants_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _malicious_project(tmp_path)
    marker = project / MARKER_NAME
    for raw in ("1", "true", "YES", "on", "True"):
        monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", raw)
        assert hosted_project_exec_allowed() is False
        with pytest.raises(HostedCustomerExecutionRemoved):
            _make_adapter({"target": PRODUCT_TARGET, "project_path": str(project)})
        assert not marker.exists()


def test_hosted_never_calls_load_adapter_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _malicious_project(tmp_path)
    with patch(
        "mutiny_openai_agents.loader.load_adapter_factory",
        side_effect=AssertionError("load_adapter_factory must not run"),
    ) as mocked:
        with pytest.raises(HostedCustomerExecutionRemoved):
            validate_campaign_config(
                {"target": PRODUCT_TARGET, "project_path": str(project)}
            )
        with pytest.raises(HostedCustomerExecutionRemoved):
            _make_adapter({"target": PRODUCT_TARGET, "project_path": str(project)})
        mocked.assert_not_called()


def test_local_cli_loader_unaffected_by_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI/local load_adapter_factory still executes customer adapters."""
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
    """Trusted in_process_demo does not need any exec flag."""
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    cfg = validate_campaign_config({"target": "in_process_demo"})
    adapter = _make_adapter(cfg)
    assert adapter.__class__.__name__ == "InProcessDemoAdapter"


def test_alias_exception_is_same_type() -> None:
    assert HostedProjectExecDisabled is HostedCustomerExecutionRemoved
