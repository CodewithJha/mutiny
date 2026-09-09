"""AttackFocus — policy-conditioned mutation targeting."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mutiny_core.policy.models import PolicySet


class AttackFocus(BaseModel):
    """Structured probe targets derived from a PolicySet.

    Used by seed/mutator code to choose *what* boundary to explore.
    Must not be dumped verbatim as instructions to the target agent.
    """

    tools: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    critical_args: list[str] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)
    # arg -> exclusive lower bound style threshold (from gt/gte)
    numeric_thresholds: dict[str, float] = Field(default_factory=dict)
    # arg -> concrete eq/ne probe values (forbid/require equality)
    equality_probes: dict[str, Any] = Field(default_factory=dict)


def derive_attack_focus(policy_set: PolicySet) -> AttackFocus:
    tools: list[str] = []
    rule_ids: list[str] = []
    critical: list[str] = []
    kinds: list[str] = []
    numeric_thresholds: dict[str, float] = {}
    equality_probes: dict[str, Any] = {}

    for rule in policy_set.rules:
        rule_ids.append(rule.id)
        kind = rule.kind.value if hasattr(rule.kind, "value") else str(rule.kind)
        if kind not in kinds:
            kinds.append(kind)
        if rule.tool not in tools:
            tools.append(rule.tool)
        for mapping in (rule.when, rule.require, rule.forbid):
            if not mapping:
                continue
            for key, constraint in mapping.items():
                if key not in critical:
                    critical.append(key)
                if constraint.gt is not None:
                    numeric_thresholds[key] = float(constraint.gt)
                elif constraint.gte is not None:
                    # Treat gte N as boundary at N (nudge probes use > threshold-ε)
                    numeric_thresholds.setdefault(key, float(constraint.gte))
                elif constraint.lt is not None:
                    numeric_thresholds.setdefault(key, float(constraint.lt))
                elif constraint.lte is not None:
                    numeric_thresholds.setdefault(key, float(constraint.lte))
                if constraint.eq is not None and not (
                    isinstance(constraint.eq, str)
                    and constraint.eq.startswith("$context.")
                ):
                    equality_probes[key] = constraint.eq
                if constraint.ne is not None and not (
                    isinstance(constraint.ne, str)
                    and constraint.ne.startswith("$context.")
                ):
                    # Probe the disallowed-equal case by naming the arg
                    equality_probes.setdefault(key, constraint.ne)

    return AttackFocus(
        tools=tools,
        rule_ids=rule_ids,
        critical_args=critical,
        kinds=kinds,
        numeric_thresholds=numeric_thresholds,
        equality_probes=equality_probes,
    )
