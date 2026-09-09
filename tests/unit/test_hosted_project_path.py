"""Unit: Hosted project_path helpers (policies metadata) — customer exec retired."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_api.supervisor import (
    PRODUCT_TARGET,
    HostedCustomerExecutionRemoved,
    _make_adapter,
    resolve_project_root,
    validate_campaign_config,
)

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "examples" / "openai_support_agent"


def test_resolve_project_root_absolute() -> None:
    root = resolve_project_root(SAMPLE)
    assert root == SAMPLE.resolve()


def test_resolve_project_root_relative() -> None:
    root = resolve_project_root("examples/openai_support_agent")
    assert root == SAMPLE.resolve()


def test_resolve_rejects_missing_adapter(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        resolve_project_root(tmp_path)


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
