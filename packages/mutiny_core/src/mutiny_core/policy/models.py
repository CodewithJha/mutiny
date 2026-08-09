"""PolicySet / PolicyRule / PolicyHit — SYSTEM_DESIGN §6."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from mutiny_core.policy.constraints import ArgConstraint


class RuleKind(str, Enum):
    DENY_TOOL = "deny_tool"
    REQUIRE_ARGS = "require_args"
    FORBID_ARGS = "forbid_args"


class PolicyRule(BaseModel):
    """Machine-checkable tool-use invariant."""

    id: str
    description: str
    tool: str
    kind: RuleKind
    when: dict[str, ArgConstraint] | None = None
    require: dict[str, ArgConstraint] | None = None
    forbid: dict[str, ArgConstraint] | None = None
    deny: bool | None = None

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> PolicyRule:
        if self.kind == RuleKind.REQUIRE_ARGS:
            if not self.require:
                raise ValueError("require_args rules must set non-empty `require`")
            if self.forbid is not None:
                raise ValueError("require_args rules must not set `forbid`")
            if self.deny is not None:
                raise ValueError("require_args rules must not set `deny`")
        elif self.kind == RuleKind.FORBID_ARGS:
            if not self.forbid:
                raise ValueError("forbid_args rules must set non-empty `forbid`")
            if self.require is not None:
                raise ValueError("forbid_args rules must not set `require`")
            if self.when is not None:
                raise ValueError("forbid_args rules must not set `when` (use forbid only)")
            if self.deny is not None:
                raise ValueError("forbid_args rules must not set `deny`")
        elif self.kind == RuleKind.DENY_TOOL:
            if self.require is not None or self.forbid is not None or self.when is not None:
                raise ValueError(
                    "deny_tool rules must not set when/require/forbid"
                )
            if self.deny is False:
                raise ValueError("deny_tool with deny=false is a no-op; omit or set true")
        return self


class PolicySet(BaseModel):
    version: str
    target: str
    rules: list[PolicyRule] = Field(default_factory=list)


class PolicyEvidence(BaseModel):
    """Human-readable violation / near-miss evidence."""

    rule_id: str
    message: str
    tool_name: str | None = None
    tool_call_id: str | None = None
    arguments: dict[str, Any] | None = None
    matched_when: bool | None = None
    failed_constraints: list[str] | None = None


class PolicyHit(BaseModel):
    """Per-rule evaluation result. violated is binary and deterministic."""

    rule_id: str
    violated: bool
    evidence: PolicyEvidence
    proximity: float = Field(ge=0.0, le=1.0)
