#!/usr/bin/env python3
"""Backup demo path — fixture oracle + regression replay without live search.

Proves DEMO_SCRIPT §4 nuclear option: walk a checked-in violation + regression
artifact when live campaign search fails. Never invents fake DB rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "examples" / "traces" / "m4_refund_limit_violation.json"
REGRESSION = ROOT / "examples" / "regressions" / "refund_limit_m5.json"
POLICY = ROOT / "examples" / "policies" / "demo_support.json"


def main() -> int:
    from demo_agent import InProcessDemoAdapter
    from demo_agent.agent import DemoSupportAgent
    from mutiny_core import (
        ExecutionTrace,
        PolicyEvaluator,
        PolicySet,
        RegressionTest,
        ToolCall,
        TraceTurn,
        replay_regression,
    )

    policy = PolicySet.model_validate_json(POLICY.read_text())
    fixture = json.loads(TRACE.read_text())
    tc0 = fixture["tool_calls"][0]
    tool = ToolCall(id=tc0["id"], name=tc0["name"], arguments=tc0["arguments"])
    trace = ExecutionTrace(
        candidate_id="backup-fixture",
        session_id="backup-fixture",
        turns=[
            TraceTurn(
                user_message=fixture["genome"]["messages"][0]["content"],
                assistant_message="",
                tool_calls=[tool],
            )
        ],
        all_tool_calls=[tool],
    )
    hits = PolicyEvaluator().evaluate(policy, trace, {"refund_limit": 200})
    violated = any(h.violated and h.rule_id == "refund_limit" for h in hits)
    print(f"fixture oracle refund_limit violated={violated}")
    if not violated:
        print(
            "BACKUP FIXTURE FAILED: oracle did not see refund_limit",
            file=sys.stderr,
        )
        return 1

    art = RegressionTest.model_validate_json(REGRESSION.read_text())
    soft = InProcessDemoAdapter(agent=DemoSupportAgent(enforce_refund_policy=False))
    before = replay_regression(art, adapter=soft, policy_set=policy)
    print(f"regression replay status={before.status} (expect FAIL before fix)")
    if before.status != "FAIL":
        print(
            f"BACKUP FIXTURE FAILED: expected FAIL got {before.status}",
            file=sys.stderr,
        )
        return 1

    fixed = InProcessDemoAdapter(agent=DemoSupportAgent(enforce_refund_policy=True))
    after = replay_regression(art, adapter=fixed, policy_set=policy)
    print(f"after fix status={after.status} (expect PASS)")
    if after.status != "PASS":
        print(
            f"BACKUP FIXTURE FAILED: expected PASS got {after.status}",
            file=sys.stderr,
        )
        return 1

    print("BACKUP FIXTURE PATH OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
