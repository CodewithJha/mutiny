"""AttackFocus — policy-conditioned mutation targeting."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mutiny_core.policy.models import PolicySet


class AttackFocus(BaseModel):
    tools: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    critical_args: list[str] = Field(default_factory=list)


def derive_attack_focus(policy_set: PolicySet) -> AttackFocus:
    tools: list[str] = []
    rule_ids: list[str] = []
    critical: list[str] = []
    for rule in policy_set.rules:
        rule_ids.append(rule.id)
        if rule.tool not in tools:
            tools.append(rule.tool)
        for mapping in (rule.when, rule.require, rule.forbid):
            if mapping:
                for key in mapping:
                    if key not in critical:
                        critical.append(key)
    return AttackFocus(tools=tools, rule_ids=rule_ids, critical_args=critical)
