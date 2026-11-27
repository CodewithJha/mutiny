"""Regression artifacts — save gate + deterministic replay."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from mutiny_core.adapter.port import TargetAdapter
from mutiny_core.adapter.runner import execute_conversation
from mutiny_core.minimize import MinimizeResult
from mutiny_core.policy.evaluator import PolicyEvaluator
from mutiny_core.policy.models import PolicySet
from mutiny_core.trace.models import ExecutionTrace


class RegressionNotReproducibleError(ValueError):
    """Raised when save is refused because the exploit does not re-verify."""


class RegressionInconclusiveError(RuntimeError):
    """Raised when a replay cannot check the rules a regression guards.

    Reporting PASS would be a false green and FAIL is unproven; callers should
    surface the reason (CLI and Hosted report the case as SKIPPED).
    """


class RegressionExpected(BaseModel):
    must_not_violate: list[str] = Field(default_factory=list)


class RegressionProvenance(BaseModel):
    campaign_id: str | None = None
    candidate_id: str | None = None
    minimized_from_turns: int
    minimized_turn_count: int
    rule_ids: list[str] = Field(default_factory=list)
    # Policy set version in force when the regression was saved (no migrations).
    policy_version: str | None = None


class RegressionTest(BaseModel):
    """Permanent regression artifact — SYSTEM_DESIGN §8."""

    version: str = "1"
    name: str
    target: str
    policy_rule_ids: list[str]
    conversation: list[str]
    expected: RegressionExpected
    provenance: RegressionProvenance


class ReplayResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    violated_rule_ids: list[str] = Field(default_factory=list)
    trace: ExecutionTrace | None = None


def build_regression(
    minimized: MinimizeResult,
    *,
    name: str,
    target: str,
    policy_set: PolicySet,
) -> RegressionTest:
    """Build artifact from a successful minimize result (does not re-check)."""
    rules = list(minimized.target_rule_ids)
    return RegressionTest(
        name=name,
        target=target,
        policy_rule_ids=rules,
        conversation=[m.content for m in minimized.minimized_genome.messages],
        expected=RegressionExpected(must_not_violate=rules),
        provenance=RegressionProvenance(
            campaign_id=minimized.campaign_id,
            candidate_id=minimized.candidate_id,
            minimized_from_turns=minimized.original_turn_count,
            minimized_turn_count=minimized.minimized_turn_count,
            rule_ids=rules,
            policy_version=policy_set.version,
        ),
    )


def save_regression(
    minimized: MinimizeResult,
    *,
    name: str,
    target: str,
    policy_set: PolicySet,
) -> RegressionTest:
    """Create a regression only if ``still_reproduces`` is true."""
    if not minimized.still_reproduces:
        raise RegressionNotReproducibleError(
            "refusing to save regression: minimized conversation does not "
            "reproduce the target policy violation under re-execution"
        )
    if minimized.minimized_turn_count < 1:
        raise RegressionNotReproducibleError(
            "refusing to save regression: empty conversation"
        )
    return build_regression(
        minimized, name=name, target=target, policy_set=policy_set
    )


def replay_regression(
    artifact: RegressionTest,
    *,
    adapter: TargetAdapter,
    policy_set: PolicySet,
) -> ReplayResult:
    """Re-exec conversation; PASS iff none of must_not_violate rules fire.

    Uses the same PolicyEvaluator as live campaigns. No LLM judging.

    Raises ``RegressionInconclusiveError`` instead of returning PASS when the
    guarded rules could not be checked: a rule is missing from *policy_set*,
    the artifact has no rules or no conversation, or the target errored before
    the conversation finished without a guarded rule firing.
    """
    must_not = list(artifact.expected.must_not_violate) or list(
        artifact.policy_rule_ids
    )
    if not must_not:
        raise RegressionInconclusiveError(
            "regression lists no policy rules to check"
        )
    known = {rule.id for rule in policy_set.rules}
    missing = [rid for rid in must_not if rid not in known]
    if missing:
        raise RegressionInconclusiveError(
            "regression guards rule(s) missing from the current policy: "
            f"{', '.join(missing)} (renamed or removed?)"
        )
    if not artifact.conversation:
        raise RegressionInconclusiveError("regression has an empty conversation")
    trace = execute_conversation(
        adapter,
        list(artifact.conversation),
        candidate_id=f"replay-{artifact.name}",
        session_id=f"replay-{artifact.name}",
    )
    context = adapter.context(f"replay-{artifact.name}")
    hits = PolicyEvaluator().evaluate(policy_set, trace, context)
    violated = [h.rule_id for h in hits if h.violated and h.rule_id in must_not]
    if violated:
        return ReplayResult(status="FAIL", violated_rule_ids=violated, trace=trace)
    if trace.status == "error":
        raise RegressionInconclusiveError(
            f"replay did not finish: {trace.error or 'target error'}"
        )
    return ReplayResult(status="PASS", violated_rule_ids=[], trace=trace)
