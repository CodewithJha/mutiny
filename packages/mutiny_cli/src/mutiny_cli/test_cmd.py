"""``mutiny test`` — replay project-local regressions via Core ``replay_regression``."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mutiny_core import PolicyValidationError, load_project_policy
from mutiny_core.regress import RegressionTest, ReplayResult, replay_regression
from mutiny_openai_agents.loader import ensure_project_on_path, load_adapter_factory

Status = Literal["PASS", "FAIL", "SKIPPED"]

REPORT_REL = Path(".mutiny") / "test-report.json"
TESTS_DIR = Path(".mutiny") / "tests"


@dataclass
class CaseResult:
    id: str
    name: str
    path: str
    status: Status
    duration_ms: float
    policy_version: str | None = None
    rule_ids: list[str] = field(default_factory=list)
    violated_rule_ids: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    summary: str = ""


@dataclass
class TestReport:
    generated_at: str
    project: str
    policy_version: str | None
    results: list[CaseResult]
    passed: int
    failed: int
    skipped: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "project": self.project,
            "policy_version": self.policy_version,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "results": [asdict(r) for r in self.results],
        }


def run_tests(
    *,
    project_root: Path,
    regression_id: str | None = None,
    failed_only: bool = False,
    json_out: bool = False,
    write_report: bool = True,
) -> int:
    """Discover and replay project regressions. Exit 0 all pass, 1 failures, 2 error."""
    root = project_root.resolve()
    ensure_project_on_path(root)

    try:
        policy, policy_path = load_project_policy(root)
    except PolicyValidationError as exc:
        print(f"error: invalid project policy — {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(
            f"error: {exc}\n"
            "  hint: run `mutiny init` or add policy.yaml / .mutiny/policy.yaml",
            file=sys.stderr,
        )
        return 2

    cases = discover_regressions(root)
    if not cases:
        print()
        print("Mutiny test — no regressions found")
        print(f"  looked in  {root / TESTS_DIR}")
        print()
        print(
            "  Save a regression after a verified violation "
            "(CLI local run writes `.mutiny/tests/<name>.json`)."
        )
        print(
            "  Note: Hosted-only regressions live in the Hosted SQLite DB — "
            "re-save locally or copy the artifact JSON into `.mutiny/tests/` "
            "to run them with `mutiny test`."
        )
        print()
        return 0

    if failed_only:
        prev_failed = _failed_ids_from_report(root)
        if prev_failed is None:
            print(
                "error: --failed requires a prior report at "
                f"{REPORT_REL} (run `mutiny test` once first)",
                file=sys.stderr,
            )
            return 2
        cases = [c for c in cases if c["id"] in prev_failed or c["name"] in prev_failed]
        if not cases:
            print("No previously failed regressions to re-run.")
            return 0

    if regression_id:
        selected = _select_case(cases, regression_id)
        if selected is None:
            ids = ", ".join(c["id"] for c in cases)
            print(
                f"error: regression {regression_id!r} not found.\n"
                f"  available: {ids}",
                file=sys.stderr,
            )
            return 2
        cases = [selected]

    try:
        factory = load_adapter_factory(root)
        adapter = factory()
    except Exception as exc:  # noqa: BLE001
        print(
            f"error: could not load .mutiny/adapter.py — {exc}\n"
            "  hint: ensure create_adapter() imports cleanly",
            file=sys.stderr,
        )
        return 2

    if not json_out:
        print()
        print("Mutiny test — regression replay")
        print(f"  project: {root}")
        print(
            f"  policy:  {policy_path.name} · v{policy.version} · "
            f"{len(policy.rules)} rule(s)"
        )
        print(f"  cases:   {len(cases)}")
        print()

    results: list[CaseResult] = []
    for case in cases:
        result = _run_one(case, adapter=adapter, policy=policy)
        results.append(result)
        if not json_out:
            _print_line(result)

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIPPED")

    report = TestReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        project=str(root),
        policy_version=policy.version,
        results=results,
        passed=passed,
        failed=failed,
        skipped=skipped,
    )

    if write_report:
        out_path = root / REPORT_REL
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )

    if json_out:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print()
        print(f"Summary: {passed} Passed / {failed} Failed / {skipped} Skipped")
        if write_report:
            print(f"Report:  {REPORT_REL}")
        print()
        for r in results:
            if r.status == "FAIL":
                rules = ", ".join(r.violated_rule_ids) or "—"
                print(f"  FAIL {r.name}: still violates {rules}")
                if r.evidence:
                    tools = ", ".join(
                        str(e.get("tool") or e.get("name") or "?") for e in r.evidence[:4]
                    )
                    print(f"         evidence tools: {tools}")
                if r.summary:
                    print(f"         {r.summary}")

    if failed:
        return 1
    if skipped and not passed:
        return 1
    return 0


def discover_regressions(project_root: Path) -> list[dict[str, Any]]:
    """Load RegressionTest JSON files from ``.mutiny/tests/``."""
    tests_dir = project_root / TESTS_DIR
    if not tests_dir.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(tests_dir.glob("*.json")):
        try:
            artifact = RegressionTest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except Exception:  # noqa: BLE001
            found.append(
                {
                    "id": path.stem,
                    "name": path.stem,
                    "path": path,
                    "artifact": None,
                    "load_error": f"invalid regression JSON: {path.name}",
                }
            )
            continue
        found.append(
            {
                "id": path.stem,
                "name": artifact.name,
                "path": path,
                "artifact": artifact,
                "load_error": None,
            }
        )
    return found


def _select_case(
    cases: list[dict[str, Any]], regression_id: str
) -> dict[str, Any] | None:
    key = regression_id.strip()
    for c in cases:
        if c["id"] == key or c["name"] == key:
            return c
        if Path(c["path"]).name == key:
            return c
    return None


def _failed_ids_from_report(root: Path) -> set[str] | None:
    report_path = root / REPORT_REL
    if not report_path.is_file():
        return None
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    failed: set[str] = set()
    for row in data.get("results") or []:
        if row.get("status") == "FAIL":
            if row.get("id"):
                failed.add(str(row["id"]))
            if row.get("name"):
                failed.add(str(row["name"]))
    return failed


def _run_one(case: dict[str, Any], *, adapter: Any, policy: Any) -> CaseResult:
    case_id = str(case["id"])
    name = str(case["name"])
    path = str(case["path"])
    if case.get("load_error") or case.get("artifact") is None:
        return CaseResult(
            id=case_id,
            name=name,
            path=path,
            status="SKIPPED",
            duration_ms=0.0,
            policy_version=getattr(policy, "version", None),
            error=str(case.get("load_error") or "missing artifact"),
            summary=str(case.get("load_error") or "skipped"),
        )

    artifact: RegressionTest = case["artifact"]
    rule_ids = list(artifact.expected.must_not_violate) or list(
        artifact.policy_rule_ids
    )
    t0 = time.perf_counter()
    try:
        replay: ReplayResult = replay_regression(
            artifact, adapter=adapter, policy_set=policy
        )
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        evidence = _evidence_from_replay(replay)
        summary = (
            f"violated {', '.join(replay.violated_rule_ids)}"
            if replay.status == "FAIL"
            else "no must_not_violate hits"
        )
        return CaseResult(
            id=case_id,
            name=artifact.name,
            path=path,
            status=replay.status,
            duration_ms=duration_ms,
            policy_version=policy.version,
            rule_ids=rule_ids,
            violated_rule_ids=list(replay.violated_rule_ids),
            evidence=evidence,
            summary=summary,
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return CaseResult(
            id=case_id,
            name=artifact.name,
            path=path,
            status="SKIPPED",
            duration_ms=duration_ms,
            policy_version=policy.version,
            rule_ids=rule_ids,
            error=str(exc),
            summary=f"replay error: {exc}",
        )


def _evidence_from_replay(replay: ReplayResult) -> list[dict[str, Any]]:
    if not replay.trace:
        return []
    out: list[dict[str, Any]] = []
    for call in replay.trace.all_tool_calls[:12]:
        out.append(
            {
                "tool": call.name,
                "arguments": dict(call.arguments or {}),
                "id": call.id,
            }
        )
    return out


def _print_line(result: CaseResult) -> None:
    name = result.name
    pad = max(2, 28 - len(name))
    dots = "." * pad
    if result.status == "PASS":
        mark = "✓"
    elif result.status == "FAIL":
        mark = "✗"
    else:
        mark = "○"
    print(
        f"{mark} {name} {dots} {result.status}  "
        f"({result.duration_ms:.0f}ms · "
        f"rules={','.join(result.rule_ids) or '—'} · "
        f"policy v{result.policy_version or '?'})"
    )
