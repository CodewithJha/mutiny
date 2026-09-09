"""Hosted supervisor: customer product campaigns retired; harness policy remains."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_api.supervisor import (
    HostedCustomerExecutionRemoved,
    load_policy_for_config,
    validate_campaign_config,
)


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "openai_support_agent"


def test_product_campaign_validate_retired(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        validate_campaign_config(
            {
                "target": "openai_agents",
                "project_path": str(SAMPLE),
                "population_size": 4,
                "max_generations": 1,
                "elite_count": 1,
                "max_turns": 3,
                "stop_on_first_violation": True,
            }
        )


def test_product_policy_load_retired(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    with pytest.raises(HostedCustomerExecutionRemoved, match="removed"):
        load_policy_for_config(
            {
                "target": "openai_agents",
                "project_path": str(SAMPLE),
            }
        )


def test_harness_still_uses_demo_fixture():
    cfg = {"target": "in_process_demo"}
    policy = load_policy_for_config(cfg)
    assert policy.target == "demo_support_agent"


def test_invalid_project_policy_never_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """M-PR8E refuses before policy schema validation for product targets."""
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    mutiny = tmp_path / ".mutiny"
    mutiny.mkdir()
    (mutiny / "adapter.py").write_text(
        "def create_adapter():\n    raise RuntimeError('unused')\n",
        encoding="utf-8",
    )
    (tmp_path / "policy.yaml").write_text(
        "version: '1'\ntarget: t\nrules: bad\n", encoding="utf-8"
    )
    with pytest.raises(HostedCustomerExecutionRemoved):
        validate_campaign_config(
            {
                "target": "openai_agents",
                "project_path": str(tmp_path),
            }
        )
