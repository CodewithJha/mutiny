"""M3: template/structural mutations + AttackFocus."""

from __future__ import annotations

from mutiny_core.genome import AttackGenome, AttackMessage
from mutiny_core.mutate import AttackFocus, TemplateMutator, derive_attack_focus
from mutiny_core.policy import (
    ArgConstraint,
    PolicyRule,
    PolicySet,
    RuleKind,
)


def _refund_policy() -> PolicySet:
    return PolicySet(
        version="1",
        target="t",
        rules=[
            PolicyRule(
                id="refund_limit",
                description="x",
                tool="issue_refund",
                kind=RuleKind.REQUIRE_ARGS,
                when={"amount": ArgConstraint(gt=200)},
                require={"approved": ArgConstraint(eq=True)},
            )
        ],
    )


def test_derive_attack_focus_extracts_tool_and_rule():
    focus = derive_attack_focus(_refund_policy())
    assert isinstance(focus, AttackFocus)
    assert "issue_refund" in focus.tools
    assert "refund_limit" in focus.rule_ids


def test_template_mutation_preserves_lineage():
    parent = AttackGenome(
        id="parent-1",
        parent_id=None,
        generation=0,
        strategy="seed",
        mutations=[],
        target_rule_ids=["refund_limit"],
        messages=[AttackMessage(content="Please refund order ord_1001 for $50")],
    )
    mutator = TemplateMutator(rng_seed=0)
    child = mutator.mutate(parent, derive_attack_focus(_refund_policy()), generation=1)
    assert child.id != parent.id
    assert child.parent_id == parent.id
    assert child.generation == 1
    assert child.strategy.startswith("mutate:")
    assert len(child.mutations) == len(parent.mutations) + 1
    assert child.target_rule_ids == ["refund_limit"]
    assert 1 <= len(child.messages) <= 4
    for m in child.messages:
        assert 1 <= len(m.content) <= 4000


def test_multi_turn_setup_adds_message():
    parent = AttackGenome(
        id="p",
        generation=0,
        strategy="seed",
        target_rule_ids=["refund_limit"],
        messages=[AttackMessage(content="Refund ord_1001 for $100")],
    )
    mutator = TemplateMutator(rng_seed=1)
    child = mutator.apply_operator(
        parent, "multi_turn_setup", derive_attack_focus(_refund_policy()), generation=1
    )
    assert len(child.messages) == len(parent.messages) + 1
    assert child.mutations[-1] == "multi_turn_setup"


def test_mutation_respects_max_turns():
    msgs = [AttackMessage(content=f"turn {i} about ord_1001") for i in range(4)]
    parent = AttackGenome(
        id="p",
        generation=0,
        strategy="seed",
        target_rule_ids=["refund_limit"],
        messages=msgs,
    )
    mutator = TemplateMutator(rng_seed=2, max_turns=4)
    child = mutator.apply_operator(
        parent, "multi_turn_setup", derive_attack_focus(_refund_policy()), generation=1
    )
    assert len(child.messages) <= 4
