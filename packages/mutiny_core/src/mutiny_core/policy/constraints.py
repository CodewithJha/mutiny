"""Deterministic argument constraint matching.

Supports operators: eq, ne, gt, gte, lt, lte.

Context references use the form ``$context.path.to.value`` (e.g.
``$context.customer.email``). Context is supplied by the adapter; evaluation
never calls an LLM.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator


CONTEXT_PREFIX = "$context."


class ArgConstraint(BaseModel):
    """Constraint over a single tool argument (or context-resolved value)."""

    eq: Any | None = None
    ne: Any | None = None
    gt: int | float | None = None
    gte: int | float | None = None
    lt: int | float | None = None
    lte: int | float | None = None

    @model_validator(mode="after")
    def _at_least_one_operator(self) -> ArgConstraint:
        if all(
            getattr(self, op) is None
            for op in ("eq", "ne", "gt", "gte", "lt", "lte")
        ):
            raise ValueError(
                "ArgConstraint requires at least one of: eq, ne, gt, gte, lt, lte"
            )
        return self

    def operators_present(self) -> list[str]:
        return [
            op
            for op in ("eq", "ne", "gt", "gte", "lt", "lte")
            if getattr(self, op) is not None
        ]


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
    return None


def matches_constraint(
    actual: Any,
    constraint: ArgConstraint,
    *,
    context: dict[str, Any],
) -> bool:
    """Return True iff *actual* satisfies all operators on *constraint* (AND).

    Missing actual (None) fails numeric and equality checks unless comparing
    eq/ne against an explicitly resolved None (rare).
    """
    for op in constraint.operators_present():
        expected = getattr(constraint, op)
        if op in ("eq", "ne"):
            expected = resolve_context_value(expected, context)

        if op == "eq":
            if not _values_equal(actual, expected):
                return False
        elif op == "ne":
            if _values_equal(actual, expected):
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
