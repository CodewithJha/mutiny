"""Project policy load / validate helpers (Milestone B)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mutiny_core import (
    PolicyFileNotFoundError,
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
 
 
def test_resolve_missing_policy_raises_policy_file_not_found(tmp_path: Path):
    with pytest.raises(PolicyFileNotFoundError) as exc_info:
        resolve_policy_path(tmp_path)
    assert issubclass(PolicyFileNotFoundError, PolicyValidationError)
    assert isinstance(exc_info.value, PolicyValidationError)
    assert "no policy file found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Strict validation: mistakes must fail loading, not change what a rule checks
# ---------------------------------------------------------------------------

_REFUND_RULE = """
version: "1"
target: t
rules:
  - id: refund_cap
    description: approved refunds must still be at most 500
    tool: issue_refund
    kind: require_args
    {when_key}:
      amount:
        gt: 200
    require:
      approved:
        eq: true
      amount:
        gte: 0
        {cap_operator}: 500
"""


def _refund_policy_text(*, when_key: str = "when", cap_operator: str = "lte") -> str:
    return _REFUND_RULE.format(when_key=when_key, cap_operator=cap_operator)


def test_strict_policy_baseline_loads():
    policy = parse_policy_text(_refund_policy_text())
    rule = policy.rules[0]
    assert rule.when is not None and rule.when["amount"].gt == 200
    assert rule.require is not None
    assert rule.require["amount"].operators_present() == ["gte", "lte"]


@pytest.mark.parametrize("operator", ["lt_eq", "max", "LTE", "equals"])
def test_unknown_constraint_operator_rejected(operator: str):
    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(_refund_policy_text(cap_operator=operator))
    assert f"rules.0.require.amount.{operator}: unknown key" in str(excinfo.value)


def test_unknown_rule_key_rejected_with_suggestion():
    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(_refund_policy_text(when_key="wen"))
    assert "rules.0.wen: unknown key (did you mean 'when'?)" in str(excinfo.value)


def test_unknown_operator_suggestion_and_no_suggestion():
    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(_refund_policy_text(cap_operator="lte_"))
    assert "(did you mean 'lte'?)" in str(excinfo.value)

    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(_refund_policy_text(cap_operator="zzzz"))
    assert str(excinfo.value).endswith("rules.0.require.amount.zzzz: unknown key")


def test_unknown_top_level_key_rejected():
    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(
            """
version: "1"
target: t
ruels: []
"""
        )
    assert "ruels: unknown key (did you mean 'rules'?)" in str(excinfo.value)


def test_duplicate_rule_ids_rejected():
    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(
            """
version: "1"
target: t
rules:
  - {id: guard, description: d, tool: send_email, kind: deny_tool}
  - {id: other, description: d, tool: export_data, kind: deny_tool}
  - {id: guard, description: d, tool: delete_account, kind: deny_tool}
  - {id: guard, description: d, tool: issue_refund, kind: deny_tool}
"""
        )
    assert "duplicate rule id(s): guard" in str(excinfo.value)
    assert "other" not in str(excinfo.value)


@pytest.mark.parametrize("field", ["id", "tool"])
def test_empty_rule_id_or_tool_rejected(field: str):
    rule = {"id": "guard", "description": "d", "tool": "send_email", "kind": "deny_tool"}
    rule[field] = ""
    with pytest.raises(PolicyValidationError) as excinfo:
        parse_policy_text(yaml.safe_dump({"version": "1", "target": "t", "rules": [rule]}))
    assert f"rules.0.{field}:" in str(excinfo.value)


def test_strict_validation_applies_to_models_built_in_code():
    from pydantic import ValidationError

    from mutiny_core.policy import ArgConstraint

    with pytest.raises(ValidationError):
        ArgConstraint(eq=True, equals=True)
    with pytest.raises(ValidationError):
        PolicySet.model_validate(
            {"version": "1", "target": "t", "rules": [], "notes": "x"}
        )


def test_shipped_policies_pass_strict_validation():
    paths = [
        SAMPLE / "policy.yaml",
        *sorted((ROOT / "examples" / "policies").glob("*.json")),
        *sorted((ROOT / "examples" / "policies").glob("*.yaml")),
    ]
    assert len(paths) >= 4
    for path in paths:
        assert load_policy_file(path).rules, path
