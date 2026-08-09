"""Project policy load / validate helpers (Milestone B)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mutiny_core import (
    PolicySet,
    PolicyValidationError,
    explain_rule,
    load_policy_file,
    load_project_policy,
    parse_policy_text,
    resolve_policy_path,
)
from mutiny_core.regress import build_regression
from mutiny_core.minimize import MinimizeResult
from mutiny_core.genome import AttackGenome, AttackMessage


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "openai_support_agent"
HARNESS = ROOT / "examples" / "policies" / "demo_support.json"


def test_load_sample_project_policy_yaml():
    policy, path = load_project_policy(SAMPLE)
    assert path.name == "policy.yaml"
    assert policy.version == "1"
    assert any(r.id == "refund_limit" for r in policy.rules)
    assert "require" in explain_rule(policy.rules[0]).lower() or "issue_refund" in explain_rule(
        policy.rules[0]
    )


def test_load_harness_fixture_json_still_works():
    policy = load_policy_file(HARNESS)
    assert policy.target == "demo_support_agent"
    assert policy.version == "1"


def test_resolve_prefers_policy_yaml(tmp_path: Path):
    (tmp_path / "policy.yaml").write_text(
        "version: '1'\ntarget: t\nrules: []\n", encoding="utf-8"
    )
    (tmp_path / "policy.json").write_text(
        '{"version":"2","target":"other","rules":[]}', encoding="utf-8"
    )
    assert resolve_policy_path(tmp_path).name == "policy.yaml"


def test_invalid_policy_friendly_error(tmp_path: Path):
    bad = tmp_path / "policy.yaml"
    bad.write_text("version: '1'\ntarget: t\nrules: not-a-list\n", encoding="utf-8")
    with pytest.raises(PolicyValidationError) as ei:
        load_policy_file(bad)
    assert "schema validation" in str(ei.value).lower() or "rules" in str(ei.value).lower()


def test_empty_policy_rejected():
    with pytest.raises(PolicyValidationError):
        parse_policy_text("")


def test_require_args_missing_require_rejected():
    with pytest.raises(PolicyValidationError):
        parse_policy_text(
            yaml.dump(
                {
                    "version": "1",
                    "target": "t",
                    "rules": [
                        {
                            "id": "bad",
                            "description": "x",
                            "tool": "t",
                            "kind": "require_args",
                        }
                    ],
                }
            )
        )


def test_regression_provenance_includes_policy_version():
    policy = PolicySet.model_validate_json(HARNESS.read_text())
    genome = AttackGenome(
        id="c",
        generation=0,
        strategy="seed",
        target_rule_ids=["refund_limit"],
        messages=[AttackMessage(content="Please refund order ord_1001 for $250.")],
    )
    minimized = MinimizeResult(
        original_genome=genome,
        minimized_genome=genome,
        still_reproduces=True,
        original_turn_count=1,
        minimized_turn_count=1,
        reexec_count=1,
        target_rule_ids=["refund_limit"],
        campaign_id="camp",
        candidate_id="c",
    )
    art = build_regression(
        minimized,
        name="t",
        target="demo_support_agent",
        policy_set=policy,
    )
    assert art.provenance.policy_version == policy.version
