"""Load + validate project policy files (YAML/JSON) — shared by CLI and Hosted."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from mutiny_core.policy.models import PolicyRule, PolicySet, RuleKind

POLICY_FILENAMES = ("policy.yaml", "policy.yml", "policy.json")


class PolicyValidationError(ValueError):
    """Friendly policy load/validation failure (never pass invalid sets to engines)."""

    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        details: list[str] | None = None,
    ) -> None:
        self.path = path
        self.details = details or []
        parts = [message]
        if path is not None:
            parts.append(f"path={path}")
        if self.details:
            parts.append("; ".join(self.details))
        super().__init__(" — ".join(parts))


def resolve_policy_path(project_root: Path) -> Path:
    """Locate the project's policy file (``policy.yaml`` preferred — matches ``mutiny init``)."""
    root = project_root.resolve()
    for name in POLICY_FILENAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    expected = ", ".join(POLICY_FILENAMES)
    raise PolicyValidationError(
        f"no policy file found in project (expected one of: {expected})",
        path=root,
    )


def parse_policy_text(text: str, *, source: str | Path = "<policy>") -> PolicySet:
    """Parse YAML or JSON policy text into a validated ``PolicySet``."""
    raw = text.strip()
    if not raw:
        raise PolicyValidationError(
            "policy file is empty",
            path=Path(str(source)) if source != "<policy>" else None,
        )
    source_str = str(source)
    data: Any
    # Prefer JSON when source suffix or content looks like JSON
    looks_json = source_str.endswith(".json") or raw[:1] in {"{", "["}
    if looks_json and not source_str.endswith((".yaml", ".yml")):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PolicyValidationError(
                f"invalid JSON policy: {exc}",
                path=Path(source_str) if source != "<policy>" else None,
            ) from exc
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise PolicyValidationError(
                "PyYAML is required to load YAML policy files"
            ) from exc
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise PolicyValidationError(
                f"invalid YAML policy: {exc}",
                path=Path(source_str) if source != "<policy>" else None,
            ) from exc
    return validate_policy_data(data, path=Path(source_str) if source != "<policy>" else None)


def validate_policy_data(
    data: Any, *, path: Path | None = None
) -> PolicySet:
    """Validate raw mapping against ``PolicySet`` with friendly errors."""
    if data is None:
        raise PolicyValidationError("policy is empty / null", path=path)
    if not isinstance(data, dict):
        raise PolicyValidationError(
            "policy must be a mapping with version, target, and rules",
            path=path,
        )
    try:
        return PolicySet.model_validate(data)
    except ValidationError as exc:
        details = [
            f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg')}"
            for err in exc.errors()
        ]
        raise PolicyValidationError(
            "policy failed schema validation",
            path=path,
            details=details,
        ) from exc


def load_policy_file(path: Path | str) -> PolicySet:
    """Load and validate a policy file from disk."""
    p = Path(path)
    if not p.is_file():
        raise PolicyValidationError(f"policy file not found: {p}", path=p)
    return parse_policy_text(p.read_text(encoding="utf-8"), source=p)


def load_project_policy(project_root: Path | str) -> tuple[PolicySet, Path]:
    """Load the policy file belonging to a customer project. Returns (set, path)."""
    root = Path(project_root).resolve()
    path = resolve_policy_path(root)
    return load_policy_file(path), path


def explain_rule(rule: PolicyRule) -> str:
    """Short human-readable explanation of a deterministic policy rule."""
    if rule.kind == RuleKind.DENY_TOOL:
        return f"Tool `{rule.tool}` must never be called."
    if rule.kind == RuleKind.REQUIRE_ARGS:
        when_bits = _fmt_constraints(rule.when)
        req_bits = _fmt_constraints(rule.require)
        if when_bits:
            return (
                f"When calling `{rule.tool}` and {when_bits}, "
                f"arguments must satisfy: {req_bits}."
            )
        return f"When calling `{rule.tool}`, arguments must satisfy: {req_bits}."
    if rule.kind == RuleKind.FORBID_ARGS:
        forbid_bits = _fmt_constraints(rule.forbid)
        return f"Calling `{rule.tool}` must not use arguments: {forbid_bits}."
    return rule.description


def rule_to_public(rule: PolicyRule) -> dict[str, Any]:
    """Structured rule payload for Hosted UI (includes explanation)."""
    data = rule.model_dump(mode="json")
    data["invariant"] = rule.kind.value
    data["explanation"] = explain_rule(rule)
    return data


def policy_set_to_public(policy: PolicySet) -> dict[str, Any]:
    data = policy.model_dump(mode="json")
    data["rules"] = [rule_to_public(r) for r in policy.rules]
    return data


def _fmt_constraints(constraints: dict[str, Any] | None) -> str:
    if not constraints:
        return "(none)"
    parts: list[str] = []
    for key, constraint in constraints.items():
        if hasattr(constraint, "model_dump"):
            ops = constraint.model_dump(exclude_none=True)
        elif isinstance(constraint, dict):
            ops = {k: v for k, v in constraint.items() if v is not None}
        else:
            parts.append(f"{key}={constraint!r}")
            continue
        op_str = ", ".join(f"{op} {val!r}" for op, val in ops.items())
        parts.append(f"{key} {op_str}".strip())
    return "; ".join(parts)
