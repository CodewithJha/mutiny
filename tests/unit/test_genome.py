"""Genome model smoke tests — M1 includes AttackGenome types."""

from mutiny_core.genome import AttackGenome, AttackMessage


def test_attack_genome_roundtrip():
    g = AttackGenome(
        id="g1",
        parent_id=None,
        generation=0,
        strategy="seed",
        mutations=[],
        target_rule_ids=["refund_limit"],
        messages=[AttackMessage(role="user", content="Please refund order 42")],
        metadata={},
    )
    data = g.model_dump()
    assert AttackGenome.model_validate(data).id == "g1"
    assert AttackGenome.model_validate(data).messages[0].content.startswith("Please")
