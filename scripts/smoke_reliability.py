#!/usr/bin/env python3
"""M8 reliability smoke — require ≥2/3 campaigns find refund_limit with tool evidence.

Usage (repo root):
  PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \\
    uv run python scripts/smoke_reliability.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "config" / "demo_pin.json"
POLICY_PATH = ROOT / "examples" / "policies" / "demo_support.json"


def main() -> int:
    pin = json.loads(PIN_PATH.read_text())
    from demo_agent import InProcessDemoAdapter
    from demo_agent.agent import DemoSupportAgent
    from mutiny_core import (
        CampaignConfig,
        CampaignEngine,
        PolicySet,
        boundary_refund_seeds,
    )

    policy = PolicySet.model_validate_json(POLICY_PATH.read_text())
    cfg = CampaignConfig(
        population_size=int(pin["population_size"]),
        max_generations=int(pin["max_generations"]),
        elite_count=int(pin["elite_count"]),
        stop_on_first_violation=bool(pin["stop_on_first_violation"]),
        max_turns=int(pin["max_turns"]),
    )
    seeds = [int(s) for s in pin["smoke_seeds"]]
    required = int(pin["smoke_required_hits"])
    hits = 0
    rows: list[str] = []

    for rng_seed in seeds:
        engine = CampaignEngine(
            adapter=InProcessDemoAdapter(
                agent=DemoSupportAgent(enforce_refund_policy=False)
            ),
            policy_set=policy,
            config=cfg,
            seeds=boundary_refund_seeds(),
            rng_seed=rng_seed,
        )
        result = engine.run()
        violators = [c for c in result.candidates if c.violated]
        refund_hit = False
        for c in violators:
            for h in c.hits:
                if h.rule_id == "refund_limit" and h.violated:
                    # Real tool evidence required — no synthetic inserts.
                    tools = (c.trace.all_tool_calls if c.trace else []) or []
                    if any(t.name == "issue_refund" for t in tools):
                        refund_hit = True
                        break
            if refund_hit:
                break
        if refund_hit:
            hits += 1
        rows.append(
            f"  seed={rng_seed} violated={result.violated} "
            f"refund_tool_proof={refund_hit} gens={result.generations_completed} "
            f"status={result.status}"
        )

    print("Mutiny reliability smoke")
    print(f"pin: {PIN_PATH.relative_to(ROOT)}")
    print(f"model: {pin.get('mutation_model')}")
    for line in rows:
        print(line)
    print(f"hits: {hits}/{len(seeds)} (need ≥{required})")

    if hits < required:
        print("SMOKE GATE FAILED", file=sys.stderr)
        return 1
    print("SMOKE GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
