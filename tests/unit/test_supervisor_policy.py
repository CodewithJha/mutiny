"""Hosted supervisor loads project policy for openai_agents campaigns."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_api.supervisor import (
    load_policy_for_config,
    validate_campaign_config,
)


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "openai_support_agent"


def test_product_campaign_loads_project_policy_yaml():
    cfg = validate_campaign_config(
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
    policy = load_policy_for_config(cfg)
    assert policy.version == "1"
    assert policy.target == "openai_agents_project"
    assert any(r.id == "refund_limit" for r in policy.rules)


def test_harness_still_uses_demo_fixture():
    cfg = {"target": "in_process_demo"}
    policy = load_policy_for_config(cfg)
    assert policy.target == "demo_support_agent"


def test_invalid_project_policy_blocks_campaign(tmp_path: Path):
    mutiny = tmp_path / ".mutiny"
    mutiny.mkdir()
    (mutiny / "adapter.py").write_text(
        "def create_adapter():\n    raise RuntimeError('unused')\n",
        encoding="utf-8",
    )
    (tmp_path / "policy.yaml").write_text(
        "version: '1'\ntarget: t\nrules: bad\n", encoding="utf-8"
    )
    with pytest.raises(Exception) as ei:
        validate_campaign_config(
            {
                "target": "openai_agents",
                "project_path": str(tmp_path),
            }
        )
    assert "policy" in str(ei.value).lower() or "schema" in str(ei.value).lower()
