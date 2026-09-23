"""Example policy fixtures load as PolicySet."""

from pathlib import Path

from mutiny_core.policy import PolicyEvaluator, PolicySet
from mutiny_core.trace import ExecutionTrace, ToolCall


ROOT = Path(__file__).resolve().parents[2]
DEMO_POLICY = ROOT / "examples" / "policies" / "demo_support.json"
DOMAIN_GUARD_POLICY = ROOT / "examples" / "policies" / "domain_guard.json"


def test_demo_support_policy_loads_and_catches_refund():
    policy = PolicySet.model_validate_json(DEMO_POLICY.read_text())
    assert {r.id for r in policy.rules} == {
        "refund_limit",
        "delete_requires_confirm",
        "deny_send_email",
    }
    ev = PolicyEvaluator()
    trace = ExecutionTrace(
        candidate_id="c",
        session_id="s",
        turns=[],
        all_tool_calls=[
            ToolCall(
                id="1",
                name="issue_refund",
                arguments={"amount": 850, "approved": False},
            )
        ],
        status="scored",
    )
    hits = ev.evaluate(policy, trace, {})
    by_id = {h.rule_id: h for h in hits}
    assert by_id["refund_limit"].violated is True
    assert by_id["delete_requires_confirm"].violated is False
    assert by_id["deny_send_email"].violated is False


def test_domain_guard_policy_loads_and_evaluates():
    policy = PolicySet.model_validate_json(DOMAIN_GUARD_POLICY.read_text())
    assert {r.id for r in policy.rules} == {
        "forbid_competitor_domains",
        "require_https_webhook",
        "forbid_confidential_notes",
    }
    ev = PolicyEvaluator()
    trace = ExecutionTrace(
        candidate_id="c",
        session_id="s",
        turns=[],
        all_tool_calls=[
            ToolCall(
                id="1",
                name="send_email",
                arguments={"recipient": "ceo@competitor.com"},
            ),
            ToolCall(
                id="2",
                name="register_webhook",
                arguments={"url": "https://service.internal.corp"},
            ),
            ToolCall(
                id="3",
                name="add_customer_note",
                arguments={"note": "Contains [CONFIDENTIAL] info"},
            ),
        ],
        status="scored",
    )
    hits = ev.evaluate(policy, trace, {})
    by_id = {h.rule_id: h for h in hits}
    assert by_id["forbid_competitor_domains"].violated is True
    assert by_id["require_https_webhook"].violated is False
    assert by_id["forbid_confidential_notes"].violated is True

