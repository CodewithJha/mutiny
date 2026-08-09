"""M4: real violation discovery against InProcessDemoAdapter (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from mutiny_core.campaign import (
    CampaignConfig,
    CampaignEngine,
    boundary_refund_seeds,
)
from mutiny_core.mutate import MutationEngine
from mutiny_core.policy import PolicySet

from demo_agent import InProcessDemoAdapter


ROOT = Path(__file__).resolve().parents[2]
DEMO_POLICY = ROOT / "examples" / "policies" / "demo_support.json"
TRACE_OUT = ROOT / "examples" / "traces" / "m4_refund_limit_violation.json"


def _policy() -> PolicySet:
    return PolicySet.model_validate_json(DEMO_POLICY.read_text())


def test_boundary_seeds_do_not_plant_apr4242_850_pair():
    seeds = boundary_refund_seeds()
    blob = " ".join(m.content for s in seeds for m in s.messages)
    assert "APR-4242" not in blob
    assert "$850" not in blob and "850" not in blob


def test_demo_campaign_finds_refund_limit_violation():
    """Headless campaign must discover a real issue_refund policy break."""
    config = CampaignConfig(
        population_size=8,
        max_generations=4,
        elite_count=2,
        stop_on_first_violation=True,
        max_turns=3,
    )
    engine = CampaignEngine(
        adapter=InProcessDemoAdapter(),
        policy_set=_policy(),
        config=config,
        seeds=boundary_refund_seeds(target_rule_ids=["refund_limit"]),
        mutator=MutationEngine(llm=None, rng_seed=11, max_turns=3),
        rng_seed=11,
    )
    result = engine.run()
    assert result.violated is True
    assert result.best is not None
    assert result.best.fitness == 1.0

    violators = [c for c in result.candidates if c.violated]
    assert violators
    winner = violators[0]
    refunds = [tc for tc in winner.trace.all_tool_calls if tc.name == "issue_refund"]
    assert refunds, "violation must come from a real issue_refund tool call"
    call = refunds[-1]
    assert float(call.arguments["amount"]) > 200
    assert call.arguments["approved"] is not True

    hit = next(h for h in winner.hits if h.rule_id == "refund_limit")
    assert hit.violated is True
    assert hit.evidence.arguments is not None
    assert hit.evidence.arguments["amount"] == call.arguments["amount"]


def test_demo_campaign_reliability_across_seeds():
    """Prefer ≥2/3 success on varied rng seeds (offline template path)."""
    successes = 0
    runs = 3
    for seed in (0, 1, 2):
        engine = CampaignEngine(
            adapter=InProcessDemoAdapter(),
            policy_set=_policy(),
            config=CampaignConfig(
                population_size=8,
                max_generations=4,
                elite_count=2,
                stop_on_first_violation=True,
                max_turns=3,
            ),
            seeds=boundary_refund_seeds(target_rule_ids=["refund_limit"]),
            mutator=MutationEngine(llm=None, rng_seed=seed, max_turns=3),
            rng_seed=seed,
        )
        if engine.run().violated:
            successes += 1
    assert successes >= 2, f"expected ≥2/3 violation runs, got {successes}/{runs}"


def test_mutation_path_finds_violation_from_sub_boundary_seeds():
    """With only mild seeds, guided mutator must search past $200."""
    from mutiny_core.campaign import default_refund_seeds

    engine = CampaignEngine(
        adapter=InProcessDemoAdapter(),
        policy_set=_policy(),
        config=CampaignConfig(
            population_size=8,
            max_generations=6,
            elite_count=2,
            stop_on_first_violation=True,
            max_turns=3,
        ),
        seeds=default_refund_seeds(target_rule_ids=["refund_limit"]),
        mutator=MutationEngine(llm=None, rng_seed=42, max_turns=3, guided=True),
        rng_seed=42,
    )
    result = engine.run()
    assert result.violated is True
    winner = next(c for c in result.candidates if c.violated)
    assert winner.genome.generation >= 1
    assert winner.genome.mutations
    refunds = [tc for tc in winner.trace.all_tool_calls if tc.name == "issue_refund"]
    assert refunds and float(refunds[-1].arguments["amount"]) > 200
    assert refunds[-1].arguments["approved"] is not True


def test_persist_violation_trace_artifact():
    """Write a real violating trace for inspection (M4 DoD)."""
    engine = CampaignEngine(
        adapter=InProcessDemoAdapter(),
        policy_set=_policy(),
        config=CampaignConfig(
            population_size=8,
            max_generations=4,
            elite_count=2,
            stop_on_first_violation=True,
            max_turns=3,
        ),
        seeds=boundary_refund_seeds(target_rule_ids=["refund_limit"]),
        mutator=MutationEngine(llm=None, rng_seed=5, max_turns=3),
        rng_seed=5,
    )
    result = engine.run()
    assert result.violated
    winner = next(c for c in result.candidates if c.violated)
    artifact = {
        "campaign_status": result.status,
        "generation": winner.genome.generation,
        "genome": winner.genome.model_dump(),
        "fitness": winner.fitness,
        "tool_calls": [tc.model_dump() for tc in winner.trace.all_tool_calls],
        "policy_hits": [h.model_dump() for h in winner.hits],
    }
    TRACE_OUT.parent.mkdir(parents=True, exist_ok=True)
    TRACE_OUT.write_text(json.dumps(artifact, indent=2))
    assert TRACE_OUT.exists()
    loaded = json.loads(TRACE_OUT.read_text())
    assert any(tc["name"] == "issue_refund" for tc in loaded["tool_calls"])
