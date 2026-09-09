"""M-PR3: deterministic secret redaction (unit tests A–G, policy boundary)."""

from __future__ import annotations

import json

from mutiny_core import PolicyEvaluator, PolicySet, RuleKind
from mutiny_core.policy.models import PolicyRule
from mutiny_core.redact import REDACTED, redact_secrets
from mutiny_core.trace import ExecutionTrace, ToolCall


FAKE_KEY = "fake-mutiny-secret-123"
FAKE_TOKEN = "fake-token-123"
FAKE_PASSWORD = "fake-password"
FAKE_NESTED = "fake-key"


def test_a_api_key_field_redacted() -> None:
    out = redact_secrets({"api_key": FAKE_KEY})
    blob = json.dumps(out)
    assert FAKE_KEY not in blob
    assert REDACTED in blob
    assert out["api_key"] == REDACTED


def test_b_bearer_token_redacted() -> None:
    raw = f"Authorization: Bearer {FAKE_TOKEN}"
    out = redact_secrets(raw)
    assert FAKE_TOKEN not in out
    assert REDACTED in out
    assert out.lower().startswith("authorization:")


def test_c_nested_password_redacted() -> None:
    out = redact_secrets({"user": {"password": FAKE_PASSWORD, "name": "ada"}})
    assert out["user"]["password"] == REDACTED
    assert out["user"]["name"] == "ada"
    assert FAKE_PASSWORD not in json.dumps(out)


def test_d_nested_structures_redacted() -> None:
    payload = {"user": {"credentials": {"api_key": FAKE_NESTED}}}
    out = redact_secrets(payload)
    assert out["user"]["credentials"]["api_key"] == REDACTED
    assert FAKE_NESTED not in json.dumps(out)


def test_e_lists_redacted() -> None:
    payload = {"items": [{"token": "list-secret-1"}, {"ok": True}]}
    out = redact_secrets(payload)
    assert out["items"][0]["token"] == REDACTED
    assert out["items"][1]["ok"] is True
    assert "list-secret-1" not in json.dumps(out)


def test_f_ordinary_prose_preserved() -> None:
    prose = "Please rotate the token if the secret password looks stale."
    out = redact_secrets({"note": prose, "status": "token pending"})
    assert out["note"] == prose
    assert out["status"] == "token pending"


def test_g_source_immutability() -> None:
    original = {
        "api_key": FAKE_KEY,
        "nested": {"password": FAKE_PASSWORD},
        "msg": f"Authorization: Bearer {FAKE_TOKEN}",
    }
    snapshot = json.dumps(original, sort_keys=True)
    _ = redact_secrets(original)
    assert json.dumps(original, sort_keys=True) == snapshot
    assert original["api_key"] == FAKE_KEY
    assert original["nested"]["password"] == FAKE_PASSWORD


def test_camel_case_and_authorization_keys() -> None:
    out = redact_secrets(
        {
            "apiKey": "v1",
            "access_token": "v2",
            "refresh_token": "v3",
            "passwd": "v4",
            "secret": "v5",
            "authorization": f"Bearer {FAKE_TOKEN}",
        }
    )
    for key in (
        "apiKey",
        "access_token",
        "refresh_token",
        "passwd",
        "secret",
        "authorization",
    ):
        assert out[key] == REDACTED


def test_trace_shaped_tool_arguments() -> None:
    trace = {
        "candidate_id": "c1",
        "session_id": "s1",
        "turns": [
            {
                "user_message": "hi",
                "assistant_message": "ok",
                "tool_calls": [
                    {
                        "id": "t1",
                        "name": "issue_refund",
                        "arguments": {
                            "order_id": "ord_1",
                            "amount": 500,
                            "api_key": FAKE_KEY,
                        },
                    }
                ],
                "tool_results": [
                    {
                        "headers": {
                            "Authorization": f"Bearer {FAKE_TOKEN}",
                        }
                    }
                ],
                "raw": {"authorization": "secret-header"},
            }
        ],
        "all_tool_calls": [
            {
                "id": "t1",
                "name": "issue_refund",
                "arguments": {"api_key": FAKE_KEY, "amount": 500},
            }
        ],
    }
    out = redact_secrets(trace)
    blob = json.dumps(out)
    assert FAKE_KEY not in blob
    assert FAKE_TOKEN not in blob
    assert "secret-header" not in blob
    assert out["turns"][0]["tool_calls"][0]["arguments"]["amount"] == 500
    assert out["turns"][0]["tool_calls"][0]["arguments"]["api_key"] == REDACTED


def test_policy_evaluator_still_sees_raw_runtime_data() -> None:
    """Redaction must not run before PolicyEvaluator on the live trace."""
    secret = "policy-must-still-see-amount"
    trace = ExecutionTrace(
        candidate_id="c",
        session_id="s",
        all_tool_calls=[
            ToolCall(
                id="1",
                name="issue_refund",
                arguments={
                    "order_id": "o1",
                    "amount": 850,
                    "approved": False,
                    "api_key": secret,
                },
            )
        ],
    )
    policy = PolicySet(
        version="1",
        target="t",
        rules=[
            PolicyRule(
                id="refund_limit",
                description="amount>200 requires approved",
                tool="issue_refund",
                kind=RuleKind.REQUIRE_ARGS,
                when={"amount": {"gt": 200}},
                require={"approved": {"eq": True}},
            )
        ],
    )
    hits = PolicyEvaluator().evaluate(policy, trace, {})
    assert any(h.violated for h in hits)
    assert trace.all_tool_calls[0].arguments["api_key"] == secret
    sanitized = redact_secrets(trace.model_dump(mode="json"))
    assert secret not in json.dumps(sanitized)
