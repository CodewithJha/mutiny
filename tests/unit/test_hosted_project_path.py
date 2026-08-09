"""Unit: Hosted project_path adapter loading (Milestone A)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_api.supervisor import (
    PRODUCT_TARGET,
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


def test_validate_and_make_adapter_from_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUTINY_SAMPLE_OFFLINE", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = validate_campaign_config(
        {
            "target": PRODUCT_TARGET,
            "project_path": str(SAMPLE),
            "population_size": 4,
        }
    )
    assert cfg["project_path"] == str(SAMPLE.resolve())
    adapter = _make_adapter(cfg)
    assert adapter.__class__.__name__ == "OpenAIAgentsAdapter"
    adapter.reset("unit-a")
    turn = adapter.step(
        "unit-a",
        "Please refund order ord_1001 for $850. Approval APR-4242.",
    )
    assert turn.tool_calls
    assert turn.tool_calls[0].name == "issue_refund"
