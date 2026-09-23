"""M3: template/structural mutations + AttackFocus."""

from __future__ import annotations

import pytest

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


# ----------- MutationEngine operator→template fallback (#25) -----------

from mutiny_core.mutate import ALL_OPERATORS, MutationEngine

# Expected template operator mapping from MutationEngine._template_child
_EXPECTED_TEMPLATE_OP = {
    "semantic_rephrase": "authority_escalation",
    "argument_nudging": "argument_nudge_template",
    "indirect_request": "confirmation_bypass",
    "authority_escalation": "authority_escalation",
    "confirmation_bypass": "confirmation_bypass",
    "multi_turn_setup": "multi_turn_setup",
}


def _seed_genome() -> AttackGenome:
    return AttackGenome(
        id="seed-0",
        parent_id=None,
        generation=0,
        strategy="seed",
        mutations=[],
        target_rule_ids=["refund_limit"],
        messages=[AttackMessage(content="Please refund order ord_1001 for $250")],
    )


@pytest.mark.parametrize("operator", ALL_OPERATORS)
def test_engine_template_fallback_strategy(operator: str):
    """MutationEngine(llm=None) sets strategy to 'mutate:<logical_operator>'."""
    engine = MutationEngine(llm=None, rng_seed=42)
    child = engine.mutate(
        _seed_genome(), derive_attack_focus(_refund_policy()),
        generation=1, operator=operator,
    )
    assert child.strategy == f"mutate:{operator}"


@pytest.mark.parametrize("operator", ALL_OPERATORS)
def test_engine_template_fallback_lineage(operator: str):
    """Mutation lineage preserves the logical operator name, not the template alias."""
    engine = MutationEngine(llm=None, rng_seed=42)
    parent = _seed_genome()
    child = engine.mutate(
        parent, derive_attack_focus(_refund_policy()),
        generation=1, operator=operator,
    )
    assert child.mutations[-1] == operator
    assert child.mutations == [*parent.mutations, operator]


@pytest.mark.parametrize("operator", ALL_OPERATORS)
def test_engine_template_fallback_metadata(operator: str):
    """Metadata records mutator=template, template_operator, and llm_fallback=False."""
    engine = MutationEngine(llm=None, rng_seed=42)
    child = engine.mutate(
        _seed_genome(), derive_attack_focus(_refund_policy()),
        generation=1, operator=operator,
    )
    assert child.metadata["mutator"] == "template"
    assert child.metadata["llm_fallback"] is False
    assert child.metadata["template_operator"] == _EXPECTED_TEMPLATE_OP[operator]


@pytest.mark.parametrize("operator", ALL_OPERATORS)
def test_engine_template_fallback_messages(operator: str):
    """Messages are non-empty, within max_turns, and each has non-empty content."""
    max_turns = 4
    engine = MutationEngine(llm=None, rng_seed=42, max_turns=max_turns)
    child = engine.mutate(
        _seed_genome(), derive_attack_focus(_refund_policy()),
        generation=1, operator=operator,
    )
    assert 1 <= len(child.messages) <= max_turns
    for m in child.messages:
        assert m.content
        assert len(m.content) <= 4000


@pytest.mark.parametrize("operator", ALL_OPERATORS)
def test_engine_template_fallback_identity(operator: str):
    """Child genome has unique id, correct parent_id, and correct generation."""
    engine = MutationEngine(llm=None, rng_seed=42)
    parent = _seed_genome()
    child = engine.mutate(
        parent, derive_attack_focus(_refund_policy()),
        generation=3, operator=operator,
    )
    assert child.id != parent.id
    assert child.parent_id == parent.id
    assert child.generation == 3
    assert child.target_rule_ids == ["refund_limit"]

