"""ddmin minimizer — shrink attacker messages with mandatory re-exec gate."""

from __future__ import annotations

import copy
import uuid
from typing import Sequence

from pydantic import BaseModel, Field

from mutiny_core.adapter.port import TargetAdapter
from mutiny_core.adapter.runner import execute_conversation
from mutiny_core.genome.models import AttackGenome, AttackMessage
from mutiny_core.policy.evaluator import PolicyEvaluator
from mutiny_core.policy.models import PolicySet
from mutiny_core.trace.models import ExecutionTrace


class MinimizeResult(BaseModel):
    """Outcome of minimizing a violating genome."""

    original_genome: AttackGenome
    minimized_genome: AttackGenome
    target_rule_ids: list[str]
    violated_rule_ids: list[str] = Field(default_factory=list)
    still_reproduces: bool
    reexec_count: int = 0
    original_turn_count: int
    minimized_turn_count: int
    campaign_id: str | None = None
    candidate_id: str | None = None
    last_trace: ExecutionTrace | None = None


def minimize_genome(
    genome: AttackGenome,
    *,
    adapter: TargetAdapter,
    policy_set: PolicySet,
    target_rule_ids: Sequence[str],
    campaign_id: str | None = None,
    candidate_id: str | None = None,
) -> MinimizeResult:
    """Delta-debug attacker messages; keep only subsets that preserve *same* rules.

    Reproduction = re-exec target → real trace → PolicyEvaluator → each
    ``target_rule_id`` still violated. No LLM involvement.
    """
    rules = list(target_rule_ids) or list(genome.target_rule_ids)
    original_turns = len(genome.messages)
    reexec = {"n": 0}
    evaluator = PolicyEvaluator()

    def _interesting(messages: list[AttackMessage]) -> tuple[bool, ExecutionTrace | None, list[str]]:
        if not messages:
            return False, None, []
        reexec["n"] += 1
        probe = genome.model_copy(deep=True)
        probe.messages = [m.model_copy(deep=True) for m in messages]
        probe.id = f"{genome.id}-min-{reexec['n']}"
        trace = execute_conversation(
            adapter,
            [m.content for m in messages],
            candidate_id=probe.id,
            session_id=f"minimize-{probe.id}",
        )
        context = adapter.context(f"minimize-{probe.id}")
        hits = evaluator.evaluate(policy_set, trace, context)
        violated = {h.rule_id for h in hits if h.violated}
        ok = all(rid in violated for rid in rules)
        return ok, trace, sorted(violated)

    # Verify original first
    ok0, trace0, violated0 = _interesting(list(genome.messages))
    if not ok0:
        return MinimizeResult(
            original_genome=genome,
            minimized_genome=genome.model_copy(deep=True),
            target_rule_ids=rules,
            violated_rule_ids=violated0,
            still_reproduces=False,
            reexec_count=reexec["n"],
            original_turn_count=original_turns,
            minimized_turn_count=original_turns,
            campaign_id=campaign_id,
            candidate_id=candidate_id or genome.id,
            last_trace=trace0,
        )

    current = [m.model_copy(deep=True) for m in genome.messages]
    last_trace = trace0
    last_violated = violated0

    # Classic ddmin
    n = 2
    while len(current) >= 2:
        subsets = _partition(current, n)
        reduced = False
        for i, subset in enumerate(subsets):
            complement = [m for j, chunk in enumerate(subsets) if j != i for m in chunk]
            ok, tr, viol = _interesting(complement)
            if ok:
                current = complement
                last_trace = tr
                last_violated = viol
                n = max(n - 1, 2)
                reduced = True
                break
            ok_s, tr_s, viol_s = _interesting(subset)
            if ok_s:
                current = subset
                last_trace = tr_s
                last_violated = viol_s
                n = 2
                reduced = True
                break
        if reduced:
            continue
        if n >= len(current):
            break
        n = min(len(current), n * 2)

    minimized = genome.model_copy(deep=True)
    minimized.id = str(uuid.uuid4())
    minimized.parent_id = genome.id
    minimized.messages = current
    minimized.strategy = "minimized"
    minimized.mutations = [*genome.mutations, "ddmin"]
    minimized.metadata = {
        **copy.deepcopy(genome.metadata),
        "minimized_from": genome.id,
        "original_turns": original_turns,
        "minimized_turns": len(current),
    }

    return MinimizeResult(
        original_genome=genome,
        minimized_genome=minimized,
        target_rule_ids=rules,
        violated_rule_ids=last_violated,
        still_reproduces=True,
        reexec_count=reexec["n"],
        original_turn_count=original_turns,
        minimized_turn_count=len(current),
        campaign_id=campaign_id,
        candidate_id=candidate_id or genome.id,
        last_trace=last_trace,
    )


def _partition(items: list[AttackMessage], n: int) -> list[list[AttackMessage]]:
    if n <= 1 or len(items) == 0:
        return [list(items)]
    n = min(n, len(items))
    size, rem = divmod(len(items), n)
    parts: list[list[AttackMessage]] = []
    idx = 0
    for i in range(n):
        take = size + (1 if i < rem else 0)
        parts.append(items[idx : idx + take])
        idx += take
    return [p for p in parts if p]
