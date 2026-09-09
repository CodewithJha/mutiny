"""Unit: Hosted project_path helpers — FS + exec permanently removed (P0-3 / M-PR8E)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_api.supervisor import (
    PRODUCT_TARGET,
    HostedCustomerExecutionRemoved,
    HostedFilesystemAccessRemoved,
    _make_adapter,
    project_policy_payload,
    resolve_project_root,
    validate_campaign_config,
)

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "examples" / "openai_support_agent"


def test_resolve_project_root_always_refuses() -> None:
    with pytest.raises(HostedFilesystemAccessRemoved, match="filesystem"):
        resolve_project_root(SAMPLE)


def test_resolve_project_root_refuses_relative() -> None:
    with pytest.raises(HostedFilesystemAccessRemoved, match="filesystem"):
        resolve_project_root("examples/openai_support_agent")


def test_resolve_refuses_even_without_adapter(tmp_path: Path) -> None:
    with pytest.raises(HostedFilesystemAccessRemoved, match="filesystem"):
        resolve_project_root(tmp_path)


def test_project_policy_payload_refuses() -> None:
    with pytest.raises(HostedFilesystemAccessRemoved, match="filesystem"):
        project_policy_payload(SAMPLE)


def test_validate_and_make_adapter_retired_even_with_allow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    monkeypatch.setenv("MUTINY_SAMPLE_OFFLINE", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        validate_campaign_config(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(SAMPLE),
                "population_size": 4,
            }
        )
    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        _make_adapter(
            {
                "target": PRODUCT_TARGET,
                "project_path": str(SAMPLE),
            }
        )


def test_allow_env_does_not_restore_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    with pytest.raises(HostedFilesystemAccessRemoved):
        resolve_project_root(SAMPLE)
