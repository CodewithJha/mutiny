"""Deterministic argument constraint matching.

Supports operators:
- Equality / inequality: ``eq``, ``ne``
- Numeric inequalities: ``gt``, ``gte``, ``lt``, ``lte``
- String patterns: ``contains``, ``startswith``, ``endswith``

Context references use the form ``$context.path.to.value`` (e.g.
``$context.customer.email``). Context is supplied by the adapter; evaluation
never calls an LLM.

Multiple operators on the same ``ArgConstraint`` are combined with logical AND:
all present operators must evaluate to True for the constraint to match.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, model_validator


CONTEXT_PREFIX = "$context."

CONSTRAINT_OPERATORS = (
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "startswith",
    "endswith",
)


class ArgConstraint(BaseModel):
    """Constraint over a single tool argument (or context-resolved value)."""

    eq: Any | None = None
    ne: Any | None = None
    gt: int | float | None = None
    gte: int | float | None = None
    lt: int | float | None = None
    lte: int | float | None = None
    contains: str | None = None
    startswith: str | None = None
    endswith: str | None = None

    @model_validator(mode="after")
    def _at_least_one_operator(self) -> ArgConstraint:
        if all(getattr(self, op) is None for op in CONSTRAINT_OPERATORS):
            ops = ", ".join(CONSTRAINT_OPERATORS)
            raise ValueError(f"ArgConstraint requires at least one of: {ops}")
        return self

    def operators_present(self) -> list[str]:
        return [op for op in CONSTRAINT_OPERATORS if getattr(self, op) is not None]


def resolve_context_value(ref: Any, context: dict[str, Any]) -> Any:
    """Resolve ``$context...`` refs; return other values unchanged.

    Missing paths resolve to ``None``.
    """
    if not isinstance(ref, str) or not ref.startswith(CONTEXT_PREFIX):
        return ref
    path = ref[len(CONTEXT_PREFIX) :]
    if not path:
        return None
    cur: Any = context
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _as_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("$") or "," in s:
            s = s.removeprefix("$")
            # Validate grouping before removing separators: "1,00" is not 100.
            # This also keeps $context references and currency suffixes non-numeric.
            if not re.fullmatch(r"[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", s):
                return None
            s = s.replace(",", "")
        if not s or s.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity", "+infinity"):
            return None
        try:
            if "." in s or "e" in s.lower():
                return float(s)
            return int(s)
        except (ValueError, TypeError):
            return None
    return None


def matches_constraint(
    actual: Any,
    constraint: ArgConstraint,
    *,
    context: dict[str, Any],
) -> bool:
    """Return True iff *actual* satisfies all operators on *constraint* (AND).

    Missing actual (None) fails numeric, string, and equality checks unless comparing
    eq/ne against an explicitly resolved None (rare).
    """
    for op in constraint.operators_present():
        expected = getattr(constraint, op)
        if op in ("eq", "ne", "contains", "startswith", "endswith"):
            expected = resolve_context_value(expected, context)

        if op == "eq":
            if not _values_equal(actual, expected):
                return False
        elif op == "ne":
            if _values_equal(actual, expected):
                return False
        elif op in ("contains", "startswith", "endswith"):
            if not isinstance(actual, str) or not isinstance(expected, str):
                return False
            if op == "contains" and expected not in actual:
                return False
            if op == "startswith" and not actual.startswith(expected):
                return False
            if op == "endswith" and not actual.endswith(expected):
                return False
        else:
            left = _as_number(actual)
            right = _as_number(expected)
            if left is None or right is None:
                return False
            if op == "gt" and not (left > right):
                return False
            if op == "gte" and not (left >= right):
                return False
            if op == "lt" and not (left < right):
                return False
            if op == "lte" and not (left <= right):
                return False
    return True


def _values_equal(a: Any, b: Any) -> bool:
    """Equality with numeric softening (10 == 10.0) but not bool/int collapse."""
    if isinstance(a, bool) and isinstance(b, bool):
        return a == b
    if isinstance(a, bool) or isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def describe_constraint(constraint: ArgConstraint) -> str:
    parts = []
    for op in constraint.operators_present():
        parts.append(f"{op}={getattr(constraint, op)!r}")
    return " & ".join(parts)


def matches_constraint_map(
    arguments: dict[str, Any],
    constraints: dict[str, ArgConstraint],
    *,
    context: dict[str, Any],
) -> tuple[bool, list[str]]:
    """All fields in *constraints* must match. Returns (ok, failed field descs)."""
    failed: list[str] = []
    for field, constraint in constraints.items():
        actual = arguments.get(field) if field in arguments else None
        # Missing key → treat as None for matching
        if field not in arguments:
            actual = None
        if not matches_constraint(actual, constraint, context=context):
            failed.append(f"{field} ({describe_constraint(constraint)}; got={actual!r})")
    return (len(failed) == 0, failed)
