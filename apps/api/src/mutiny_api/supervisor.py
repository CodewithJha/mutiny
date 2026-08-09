"""Campaign supervisor — concurrency=1, SSE fan-out, Core orchestration."""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from mutiny_core import (
    CampaignConfig,
    CampaignEngine,
    EventType,
    MutationEngine,
    MutinyEvent,
    PolicySet,
    PolicyValidationError,
    boundary_refund_seeds,
    load_policy_file,
    load_project_policy,
    minimize_genome,
    replay_regression,
    save_regression,
)
from mutiny_core.genome import AttackGenome
from mutiny_core.regress import RegressionNotReproducibleError, RegressionTest
from mutiny_openai_agents.loader import load_adapter_factory

from demo_agent import DemoSupportAgent, InProcessDemoAdapter

from mutiny_api.repository import Repository

REPO_ROOT = Path(__file__).resolve().parents[4]

# Product target loads customer's .mutiny/adapter.py via project_path.
# in_process_demo remains an optional local harness for reliability tests.
HARNESS_TARGET = "in_process_demo"
PRODUCT_TARGET = "openai_agents"
SUPPORTED_TARGETS = frozenset({HARNESS_TARGET, PRODUCT_TARGET})
# Local Hosted default — same sample project as Milestone A UI.
DEFAULT_SAMPLE_PROJECT = "examples/openai_support_agent"
HARNESS_POLICY_ID = "demo_support"


def _find_harness_policy() -> Path:
    """Fixture policy for ``in_process_demo`` only — not the product path."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "examples" / "policies" / "demo_support.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("examples/policies/demo_support.json not found")


HARNESS_POLICY_PATH = _find_harness_policy()
# Back-compat alias for older imports/tests
DEMO_POLICY_PATH = HARNESS_POLICY_PATH


def resolve_project_root(project_path: str | Path) -> Path:
    """Resolve and validate a customer project directory.

    Absolute paths are used as-is; relative paths resolve against the Mutiny
    repo root (handy for the sample under ``examples/…``). Requires
    ``.mutiny/adapter.py``.
    """
    raw = Path(project_path).expanduser()
    root = raw.resolve() if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    if not root.is_dir():
        raise ValueError(f"project_path is not a directory: {root}")
    adapter_file = root / ".mutiny" / "adapter.py"
    if not adapter_file.is_file():
        raise ValueError(
            f"missing {adapter_file}; expected customer Mutiny project "
            "(run `mutiny init` or point at a directory with .mutiny/adapter.py)"
        )
    return root


def validate_campaign_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Normalize + validate campaign config; ensure adapter can be loaded."""
    out = dict(cfg)
    target = out.get("target") or HARNESS_TARGET
    # Legacy allowlist name — refuse with an actionable message.
    if target == "openai_support_agent":
        raise ValueError(
            "target 'openai_support_agent' is removed; use "
            "target='openai_agents' with project_path pointing at your "
            "project (e.g. examples/openai_support_agent)"
        )
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"unsupported target={target!r}; "
            f"supported={sorted(SUPPORTED_TARGETS)}"
        )
    out["target"] = target
    if target == PRODUCT_TARGET:
        project_path = out.get("project_path")
        if not project_path or not str(project_path).strip():
            raise ValueError(
                "project_path is required when target is 'openai_agents'"
            )
        root = resolve_project_root(str(project_path))
        out["project_path"] = str(root)
        # Fail fast: factory must import + project policy must validate
        load_adapter_factory(root)
        load_project_policy(root)
    else:
        # Harness: validate fixture policy up front
        load_policy_for_config(out)
    return out


def load_policy_for_config(cfg: dict[str, Any]) -> PolicySet:
    """Load the policy set for a campaign config.

    Product path (``openai_agents`` + ``project_path``): project's ``policy.yaml``
    (same file CLI uses). Harness (``in_process_demo``): demo fixture JSON.
    """
    target = cfg.get("target") or HARNESS_TARGET
    if target == PRODUCT_TARGET:
        root = resolve_project_root(str(cfg["project_path"]))
        policy, _path = load_project_policy(root)
        return policy
    # Optional harness fixture — not the Hosted product policy source
    policy_set_id = cfg.get("policy_set_id") or HARNESS_POLICY_ID
    if policy_set_id != HARNESS_POLICY_ID:
        raise ValueError(
            f"unknown harness policy_set_id={policy_set_id!r}; "
            f"use {HARNESS_POLICY_ID!r} for in_process_demo, or "
            "target=openai_agents with project_path for project policies"
        )
    return load_policy_file(HARNESS_POLICY_PATH)


def project_policy_payload(project_path: str | Path) -> dict[str, Any]:
    """Structured policy payload for Hosted Policies API."""
    from mutiny_core import policy_set_to_public

    root = resolve_project_root(project_path)
    policy, path = load_project_policy(root)
    return {
        "id": root.name,
        "project_path": str(root),
        "path": str(path),
        "version": policy.version,
        "target": policy.target,
        "policy_set": policy_set_to_public(policy),
    }


def _make_adapter(cfg: dict[str, Any], *, fixed_agent: bool = False):
    """Construct a TargetAdapter for Hosted campaigns.

    ``in_process_demo`` — optional reliability harness (DemoSupportAgent).
    ``openai_agents`` — load ``create_adapter()`` from customer's
    ``.mutiny/adapter.py`` via ``project_path`` (same loader as CLI local).
    """
    target = cfg.get("target") or HARNESS_TARGET
    if target == HARNESS_TARGET:
        return InProcessDemoAdapter(
            agent=DemoSupportAgent(enforce_refund_policy=fixed_agent)
        )
    if target == PRODUCT_TARGET:
        root = resolve_project_root(str(cfg["project_path"]))
        factory = load_adapter_factory(root)
        if fixed_agent:
            try:
                params = inspect.signature(factory).parameters
            except (TypeError, ValueError):
                params = {}
            if "enforce_refund_policy" in params:
                return factory(enforce_refund_policy=True)
            if "fixed_agent" in params:
                return factory(fixed_agent=True)
        return factory()
    raise ValueError(f"unsupported target: {target}")


class EventHub:
    """In-process SSE fan-out per campaign."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, campaign_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subs[campaign_id].append(q)
        return q

    async def unsubscribe(self, campaign_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            subs = self._subs.get(campaign_id, [])
            if q in subs:
                subs.remove(q)

    async def publish(self, campaign_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subs.get(campaign_id, []))
        for q in subs:
            await q.put(event)


class CampaignSupervisor:
    def __init__(self, repo: Repository, hub: EventHub) -> None:
        self.repo = repo
        self.hub = hub
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread_lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def load_policy(self, policy_set_id: str = HARNESS_POLICY_ID) -> PolicySet:
        """Load harness fixture by id (product campaigns use ``load_policy_for_config``)."""
        if policy_set_id != HARNESS_POLICY_ID:
            raise ValueError(f"unknown policy_set_id: {policy_set_id}")
        return load_policy_file(HARNESS_POLICY_PATH)

    def create_campaign(self, config: dict[str, Any]) -> dict[str, Any]:
        campaign_id = str(uuid.uuid4())
        cfg = dict(config)
        project_id = cfg.pop("project_id", None)
        if project_id:
            project = self.repo.get_project(str(project_id))
            if not project:
                raise ValueError(f"unknown project_id={project_id}")
            # Prefer registered project path; reject conflicting project_path.
            incoming = cfg.get("project_path")
            if incoming and str(incoming).strip():
                try:
                    incoming_root = resolve_project_root(str(incoming))
                except (ValueError, FileNotFoundError) as exc:
                    raise ValueError(str(exc)) from exc
                if str(incoming_root) != project["path"]:
                    raise ValueError(
                        "project_path does not match registered project "
                        f"(got {incoming_root}, project has {project['path']})"
                    )
            cfg["project_path"] = project["path"]
            if not cfg.get("target"):
                cfg["target"] = project.get("adapter") or PRODUCT_TARGET
        try:
            validated = validate_campaign_config(cfg)
        except PolicyValidationError as exc:
            raise ValueError(str(exc)) from exc

        # Upsert/link a project from resolved path so Milestone A/B flows
        # (project_path only) still produce campaign → project relationships.
        linked_project_id: str | None = project_id
        project_path = validated.get("project_path")
        if project_path and not linked_project_id:
            project = self.repo.upsert_project_by_path(
                str(project_path),
                adapter=str(validated.get("target") or PRODUCT_TARGET),
            )
            linked_project_id = project["id"]
        elif linked_project_id:
            self.repo.touch_project(linked_project_id)

        return self.repo.create_campaign(
            campaign_id, validated, project_id=linked_project_id
        )

    def start_campaign(
        self,
        campaign_id: str,
        *,
        attestation: bool,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not attestation:
            raise PermissionError(
                "authorization attestation required to start a campaign"
            )
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise KeyError("campaign not found")
        if campaign["status"] != "created":
            raise RuntimeError(
                f"cannot start campaign in status={campaign['status']}"
            )
        running = self.repo.list_running_campaigns()
        if running:
            raise RuntimeError(
                "concurrent campaigns forbidden (max=1); "
                f"running={running[0]['id']}"
            )
        # Re-validate (adapter / policy may have changed since create)
        try:
            validate_campaign_config(campaign["config"])
        except PolicyValidationError as exc:
            raise ValueError(str(exc)) from exc

        self.repo.update_campaign_status(
            campaign_id,
            "running",
            metrics={
                "phase": "starting",
                "candidates_scored": 0,
                "best_fitness": 0.0,
                "violated": False,
                "mutator_mode": self._mutator_mode(),
                "request_id": request_id,
            },
        )
        self._persist_and_publish(
            campaign_id,
            "attestation.accepted",
            {
                "attestation": True,
                "request_id": request_id,
                "target": campaign["config"].get("target"),
                "project_path": campaign["config"].get("project_path"),
                "mutator_mode": self._mutator_mode(),
            },
        )
        assert self._loop is not None
        self._loop.create_task(self._run_campaign_async(campaign_id))
        return self.repo.get_campaign(campaign_id)  # type: ignore[return-value]

    def _mutator_mode(self) -> str:
        from mutiny_core import try_featherless_from_env

        return "featherless" if try_featherless_from_env() else "template"

    async def _run_campaign_async(self, campaign_id: str) -> None:
        await asyncio.to_thread(self._run_campaign_sync, campaign_id)

    def _run_campaign_sync(self, campaign_id: str) -> None:
        import time

        campaign = self.repo.get_campaign(campaign_id)
        assert campaign is not None
        cfg = campaign["config"]
        try:
            policy = load_policy_for_config(cfg)
        except PolicyValidationError as exc:
            self.repo.update_campaign_status(
                campaign_id,
                "failed",
                metrics={
                    "phase": "failed",
                    "error": str(exc),
                    "mutator_mode": self._mutator_mode(),
                },
                completed=True,
            )
            self._persist_and_publish(
                campaign_id,
                EventType.CAMPAIGN_ERROR.value,
                {"error": str(exc)},
            )
            return
        core_cfg = CampaignConfig(
            population_size=cfg["population_size"],
            max_generations=cfg["max_generations"],
            elite_count=cfg["elite_count"],
            max_turns=cfg["max_turns"],
            stop_on_first_violation=cfg["stop_on_first_violation"],
            wall_clock_seconds=cfg.get("wall_clock_seconds"),
        )
        seeds = None
        if cfg.get("use_boundary_seeds", True):
            seeds = boundary_refund_seeds(target_rule_ids=["refund_limit"])

        from mutiny_core import try_featherless_from_env

        llm = try_featherless_from_env()
        mutator_mode = "featherless" if llm is not None else "template"
        started = time.perf_counter()
        scored = {"n": 0, "best": 0.0, "violated": False}

        def on_event(ev: MutinyEvent) -> None:
            self._handle_event(campaign_id, ev)
            if ev.type == EventType.CANDIDATE_SCORED:
                scored["n"] += 1
                fit = float(ev.payload.get("fitness") or 0.0)
                scored["best"] = max(scored["best"], fit)
                if ev.payload.get("violated"):
                    scored["violated"] = True
                self.repo.update_campaign_status(
                    campaign_id,
                    "running",
                    metrics={
                        "phase": "searching",
                        "candidates_scored": scored["n"],
                        "best_fitness": scored["best"],
                        "violated": scored["violated"],
                        "mutator_mode": mutator_mode,
                        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    },
                )

        adapter = _make_adapter(cfg)
        engine = CampaignEngine(
            adapter=adapter,
            policy_set=policy,
            config=core_cfg,
            seeds=seeds,
            on_event=on_event,
            rng_seed=int(cfg.get("rng_seed", 0)),
            mutator=MutationEngine(
                llm=llm,
                rng_seed=int(cfg.get("rng_seed", 0)),
                max_turns=core_cfg.max_turns,
            ),
        )
        try:
            result = engine.run()
            status = "violation" if result.violated else "completed"
            if result.status == "error":
                status = "failed"
            metrics = {
                "phase": "done",
                "generations_completed": result.generations_completed,
                "candidates": len(result.candidates),
                "candidates_scored": scored["n"],
                "best_fitness": scored["best"],
                "violated": result.violated,
                "reason": result.reason,
                "events_emitted": result.events_emitted,
                "mutator_mode": mutator_mode,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            }
            self.repo.update_campaign_status(
                campaign_id, status, metrics=metrics, completed=True
            )
        except Exception as exc:  # noqa: BLE001
            self.repo.update_campaign_status(
                campaign_id,
                "failed",
                metrics={
                    "phase": "failed",
                    "error": str(exc),
                    "mutator_mode": mutator_mode,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                },
                completed=True,
            )
            self._persist_and_publish(
                campaign_id,
                EventType.CAMPAIGN_ERROR.value,
                {"error": str(exc)},
            )

    def _handle_event(self, campaign_id: str, ev: MutinyEvent) -> None:
        payload = dict(ev.payload)
        event_type = ev.type.value if hasattr(ev.type, "value") else str(ev.type)

        if ev.type == EventType.CANDIDATE_SCORED:
            genome = payload.get("genome") or {}
            trace = payload.get("trace")
            candidate_id = payload.get("candidate_id") or genome.get("id")
            if candidate_id and genome:
                self.repo.upsert_candidate(
                    candidate_id=candidate_id,
                    campaign_id=campaign_id,
                    parent_id=payload.get("parent_id") or genome.get("parent_id"),
                    generation=int(payload.get("generation") or genome.get("generation") or 0),
                    genome=genome,
                    fitness=payload.get("fitness"),
                    status="violator" if payload.get("violated") else "scored",
                    violated=bool(payload.get("violated")),
                    hits=payload.get("hits") or [],
                )
                if trace:
                    self.repo.upsert_trace(candidate_id, trace)

        # Strip bulky nested objects from SSE if desired — keep for M7 completeness
        self._persist_and_publish(campaign_id, event_type, payload)

    def _persist_and_publish(
        self, campaign_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        stored = self.repo.append_event(campaign_id, event_type, payload)
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.hub.publish(campaign_id, stored), loop
            )

    def minimize_candidate(
        self, candidate_id: str, *, target_rule_ids: list[str] | None
    ) -> dict[str, Any]:
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise KeyError("candidate not found")
        campaign_id = cand["campaign_id"]
        camp = self.repo.get_campaign(campaign_id)
        cfg = (camp or {}).get("config") or {}
        policy = load_policy_for_config(cfg)
        rules = target_rule_ids or ["refund_limit"]
        genome = AttackGenome.model_validate(cand["genome"])
        self._persist_and_publish(
            campaign_id,
            EventType.MINIMIZATION_STARTED.value,
            {"candidate_id": candidate_id},
        )
        adapter = _make_adapter(cfg)
        result = minimize_genome(
            genome,
            adapter=adapter,
            policy_set=policy,
            target_rule_ids=rules,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
        )
        if result.still_reproduces:
            # Persist minimized genome as updated candidate status
            self.repo.upsert_candidate(
                candidate_id=candidate_id,
                campaign_id=campaign_id,
                parent_id=cand.get("parent_id"),
                generation=cand["generation"],
                genome=result.minimized_genome.model_dump(),
                fitness=1.0,
                status="minimized",
                violated=True,
                hits=cand.get("hits") or [],
            )
            if result.last_trace:
                self.repo.upsert_trace(
                    candidate_id, result.last_trace.model_dump(mode="json")
                )
        self._persist_and_publish(
            campaign_id,
            EventType.EXPLOIT_MINIMIZED.value,
            {
                "candidate_id": candidate_id,
                "still_reproduces": result.still_reproduces,
                "original_turn_count": result.original_turn_count,
                "minimized_turn_count": result.minimized_turn_count,
                "reexec_count": result.reexec_count,
                "minimized_genome": result.minimized_genome.model_dump(),
            },
        )
        return {
            "candidate_id": candidate_id,
            "still_reproduces": result.still_reproduces,
            "original_turn_count": result.original_turn_count,
            "minimized_turn_count": result.minimized_turn_count,
            "reexec_count": result.reexec_count,
            "minimized_genome": result.minimized_genome.model_dump(),
            "target_rule_ids": result.target_rule_ids,
        }

    def save_candidate_regression(
        self,
        candidate_id: str,
        *,
        name: str,
        target_rule_ids: list[str] | None,
    ) -> dict[str, Any]:
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise KeyError("candidate not found")
        campaign_id = cand["campaign_id"]
        camp = self.repo.get_campaign(campaign_id)
        cfg = (camp or {}).get("config") or {}
        policy = load_policy_for_config(cfg)
        rules = target_rule_ids or ["refund_limit"]
        genome = AttackGenome.model_validate(cand["genome"])
        adapter = _make_adapter(cfg)
        minimized = minimize_genome(
            genome,
            adapter=adapter,
            policy_set=policy,
            target_rule_ids=rules,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
        )
        try:
            artifact = save_regression(
                minimized,
                name=name,
                target=(
                    "openai_agents"
                    if cfg.get("target") == PRODUCT_TARGET
                    else "demo_support_agent"
                ),
                policy_set=policy,
            )
        except RegressionNotReproducibleError:
            raise
        reg_id = str(uuid.uuid4())
        stored = self.repo.save_regression(
            reg_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            path=None,
            artifact=artifact.model_dump(mode="json"),
        )
        self._persist_and_publish(
            campaign_id,
            EventType.REGRESSION_CREATED.value,
            {"regression_id": reg_id, "candidate_id": candidate_id, "name": name},
        )
        return stored

    def run_tests(
        self,
        regression_id: str | None = None,
        *,
        fixed_agent: bool = False,
        regression_ids: list[str] | None = None,
        run_all: bool = False,
        failed_only: bool = False,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Replay one or many regressions via Core ``replay_regression``.

        Single-id calls keep the flat response shape used by existing clients.
        Batch calls return ``{results, passed, failed, skipped}``.
        """
        ids = self._resolve_test_ids(
            regression_id=regression_id,
            regression_ids=regression_ids,
            run_all=run_all,
            failed_only=failed_only,
        )
        if not ids:
            if regression_id:
                raise KeyError("regression not found")
            return {
                "results": [],
                "passed": 0,
                "failed": 0,
                "skipped": 0,
            }

        results = [
            self._run_one_test(rid, fixed_agent=fixed_agent, persist=persist)
            for rid in ids
        ]
        if len(ids) == 1 and regression_id and not run_all and not failed_only:
            return results[0]

        passed = sum(1 for r in results if r.get("status") == "PASS")
        failed = sum(1 for r in results if r.get("status") == "FAIL")
        skipped = sum(1 for r in results if r.get("status") == "SKIPPED")
        return {
            "results": results,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }

    def _resolve_test_ids(
        self,
        *,
        regression_id: str | None,
        regression_ids: list[str] | None,
        run_all: bool,
        failed_only: bool,
    ) -> list[str]:
        if failed_only:
            summary = self.repo.tests_summary()
            return [r["id"] for r in summary.get("failed_regressions") or []]
        if run_all:
            return [r["id"] for r in self.repo.list_regressions()]
        if regression_ids:
            return list(regression_ids)
        if regression_id:
            if not self.repo.get_regression(regression_id):
                raise KeyError("regression not found")
            return [regression_id]
        raise ValueError(
            "provide regression_id, regression_ids, run_all, or failed_only"
        )

    def _run_one_test(
        self,
        regression_id: str,
        *,
        fixed_agent: bool,
        persist: bool,
    ) -> dict[str, Any]:
        row = self.repo.get_regression(regression_id)
        if not row:
            raise KeyError("regression not found")
        artifact = RegressionTest.model_validate(row["artifact"])
        camp = self.repo.get_campaign(row.get("campaign_id") or "")
        cfg = dict((camp or {}).get("config") or {})
        if not cfg and artifact.target in {
            "openai_agents",
            "openai_support_agent",
        }:
            # Orphan regression: fall back to sample project path
            cfg = {
                "target": PRODUCT_TARGET,
                "project_path": str(
                    REPO_ROOT / "examples" / "openai_support_agent"
                ),
            }
        elif not cfg:
            cfg = {"target": HARNESS_TARGET}

        t0 = time.perf_counter()
        try:
            policy = load_policy_for_config(cfg)
            adapter = _make_adapter(cfg, fixed_agent=fixed_agent)
            result = replay_regression(
                artifact, adapter=adapter, policy_set=policy
            )
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            evidence = [
                {
                    "tool": c.name,
                    "arguments": dict(c.arguments or {}),
                    "id": c.id,
                }
                for c in (result.trace.all_tool_calls if result.trace else [])[:12]
            ]
            summary = (
                f"violated {', '.join(result.violated_rule_ids)}"
                if result.status == "FAIL"
                else "no must_not_violate hits"
            )
            status = result.status
            violated = list(result.violated_rule_ids)
            policy_version = policy.version
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            evidence = []
            summary = f"replay error: {exc}"
            status = "SKIPPED"
            violated = []
            policy_version = artifact.provenance.policy_version

        agent_version = None
        if isinstance(cfg.get("project_path"), str):
            agent_version = Path(str(cfg["project_path"])).name

        out: dict[str, Any] = {
            "regression_id": regression_id,
            "name": artifact.name,
            "status": status,
            "violated_rule_ids": violated,
            "fixed_agent": fixed_agent,
            "duration_ms": duration_ms,
            "policy_version": policy_version,
            "agent_version": agent_version,
            "evidence": evidence,
            "summary": summary,
            "rule_ids": list(artifact.expected.must_not_violate)
            or list(artifact.policy_rule_ids),
        }
        if persist:
            run_id = str(uuid.uuid4())
            stored = self.repo.save_test_run(
                run_id,
                regression_id=regression_id,
                status=status,
                duration_ms=duration_ms,
                policy_version=policy_version,
                agent_version=agent_version,
                fixed_agent=fixed_agent,
                violated_rule_ids=violated,
                evidence=evidence,
                summary=summary,
            )
            out["run_id"] = stored["id"]
            out["created_at"] = stored["created_at"]
        return out
