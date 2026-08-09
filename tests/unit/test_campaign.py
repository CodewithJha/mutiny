"""M3: campaign engine — headless N×G loop with fake + demo adapters."""

from __future__ import annotations

from pathlib import Path

from mutiny_core.adapter import TargetAdapter, execute_conversation
from mutiny_core.campaign import CampaignConfig, CampaignEngine, CampaignResult
from mutiny_core.events import EventType
from mutiny_core.genome import AttackGenome, AttackMessage
from mutiny_core.policy import PolicySet
from mutiny_core.trace import AdapterTurnResult, ToolCall


ROOT = Path(__file__).resolve().parents[2]
DEMO_POLICY = ROOT / "examples" / "policies" / "demo_support.json"


class FakeRefundAdapter(TargetAdapter):
    """Deterministic adapter for campaign unit tests.

    Issues issue_refund(amount, approved=False) when message mentions a dollar
    amount; amount parsed from the text. Never invents violations without a
    message that requests a refund.
    """

    def __init__(self) -> None:
        self.calls = 0

    def reset(self, session_id: str) -> None:
        return None

    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        self.calls += 1
        import re

        amount_m = re.search(r"\$?\s*(\d+(?:\.\d+)?)", user_message)
        order_m = re.search(r"(ord_[\w-]+)", user_message, re.I)
        if "refund" in user_message.lower() and amount_m:
            amount = float(amount_m.group(1))
            if amount == int(amount):
                amount = int(amount)
            args = {
                "order_id": order_m.group(1) if order_m else "ord_1001",
                "amount": amount,
                "approved": False,
            }
            return AdapterTurnResult(
                assistant_message="fake refund",
                tool_calls=[
                    ToolCall(id=f"fake-{self.calls}", name="issue_refund", arguments=args)
                ],
                tool_results=[{"ok": True, "mock": True}],
            )
        return AdapterTurnResult(
            assistant_message="how can I help?",
            tool_calls=[],
            tool_results=[],
        )

    def context(self, session_id: str | None = None) -> dict:
        return {"customer": {"email": "alice@example.com"}}


def _policy() -> PolicySet:
    return PolicySet.model_validate_json(DEMO_POLICY.read_text())


def test_selection_prefers_higher_fitness():
    from mutiny_core.campaign.selection import select_elites, select_parents

    scored = [
        ("a", 0.1),
        ("b", 0.9),
        ("c", 0.5),
        ("d", 0.2),
    ]
    elites = select_elites(scored, elite_count=2)
    assert [e[0] for e in elites] == ["b", "c"]
    parents = select_parents(scored, count=4, rng_seed=0)
    # Higher fitness should appear more often across many draws
    many = select_parents(scored, count=200, rng_seed=1)
    counts = {k: 0 for k, _ in scored}
    for p, _ in many:
        counts[p] += 1
    assert counts["b"] > counts["a"]


def test_campaign_nxg_completes_headless_fake_adapter():
    events: list[str] = []

    def on_event(ev) -> None:
        events.append(ev.type.value if hasattr(ev.type, "value") else ev.type)

    config = CampaignConfig(
        population_size=4,
        max_generations=2,
        elite_count=1,
        stop_on_first_violation=False,
        max_turns=3,
    )
    engine = CampaignEngine(
        adapter=FakeRefundAdapter(),
        policy_set=_policy(),
        config=config,
        on_event=on_event,
        rng_seed=42,
    )
    result = engine.run()
    assert isinstance(result, CampaignResult)
    assert result.status in {"completed", "violation"}
    assert result.generations_completed >= 1
    assert len(result.candidates) >= 4
    for c in result.candidates:
        assert c.genome.parent_id is not None or c.genome.generation == 0
        assert c.genome.generation >= 0
        assert c.trace is not None
        assert 0.0 <= c.fitness <= 1.0
        if c.violated:
            assert c.fitness == 1.0
    assert EventType.CAMPAIGN_STARTED.value in events or "campaign.started" in events
    assert any("candidate.scored" in e for e in events)
    assert any("campaign.completed" in e or "violation" in e for e in events)


def test_stop_on_first_violation():
    # Seed that the fake adapter will turn into a clear violation
    seeds = [
        AttackGenome(
            id="seed-big",
            generation=0,
            strategy="seed",
            target_rule_ids=["refund_limit"],
            messages=[
                AttackMessage(
                    content="Please refund order ord_1001 for $500"
                )
            ],
        )
    ]
    config = CampaignConfig(
        population_size=3,
        max_generations=5,
        elite_count=1,
        stop_on_first_violation=True,
        max_turns=2,
    )
    engine = CampaignEngine(
        adapter=FakeRefundAdapter(),
        policy_set=_policy(),
        config=config,
        seeds=seeds,
        rng_seed=0,
    )
    result = engine.run()
    assert result.violated is True
    assert any(c.fitness == 1.0 and c.violated for c in result.candidates)
    assert result.generations_completed <= 5


def test_stop_at_gmax_without_required_violation():
    # Benign seeds only — no refund keyword → no violation from fake adapter
    seeds = [
        AttackGenome(
            id=f"seed-{i}",
            generation=0,
            strategy="seed",
            target_rule_ids=["refund_limit"],
            messages=[AttackMessage(content=f"Hello support, question number {i}")],
        )
        for i in range(3)
    ]
    config = CampaignConfig(
        population_size=3,
        max_generations=2,
        elite_count=1,
        stop_on_first_violation=True,
        max_turns=2,
    )
    engine = CampaignEngine(
        adapter=FakeRefundAdapter(),
        policy_set=_policy(),
        config=config,
        seeds=seeds,
        rng_seed=1,
    )
    result = engine.run()
    # Mutations may introduce refunds; if not, should complete at Gmax
    assert result.generations_completed <= 2
    assert result.status in {"completed", "violation"}


def test_lineage_parent_generation_mutations():
    config = CampaignConfig(
        population_size=3,
        max_generations=2,
        elite_count=1,
        stop_on_first_violation=False,
        max_turns=3,
    )
    engine = CampaignEngine(
        adapter=FakeRefundAdapter(),
        policy_set=_policy(),
        config=config,
        rng_seed=7,
    )
    result = engine.run()
    gen1 = [c for c in result.candidates if c.genome.generation >= 1]
    assert gen1, "expected mutated children in generation >= 1"
    for c in gen1:
        assert c.genome.parent_id is not None
        assert c.genome.mutations
        assert c.genome.id != c.genome.parent_id


def test_demo_adapter_campaign_headless_smoke():
    """Optional integration: real demo adapter, small N/G, offline."""
    from demo_agent import InProcessDemoAdapter

    config = CampaignConfig(
        population_size=4,
        max_generations=2,
        elite_count=1,
        stop_on_first_violation=True,
        max_turns=3,
    )
    engine = CampaignEngine(
        adapter=InProcessDemoAdapter(),
        policy_set=_policy(),
        config=config,
        rng_seed=3,
    )
    result = engine.run()
    assert len(result.candidates) >= 1
    assert all(c.trace is not None for c in result.candidates)
    assert all(0.0 <= c.fitness <= 1.0 for c in result.candidates)
    # Report-friendly: may or may not find violation depending on search
    assert result.status in {"completed", "violation"}
