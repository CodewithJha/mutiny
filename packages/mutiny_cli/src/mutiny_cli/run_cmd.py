"""``mutiny run`` — local Core by default; ``--hosted`` = local + Hosted sync."""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mutiny_core import (
    CampaignConfig,
    CampaignEngine,
    EventType,
    MutationEngine,
    MutinyEvent,
    PolicySet,
    PolicyValidationError,
    default_policy_seeds,
    load_project_policy,
    minimize_genome,
    save_regression,
    try_featherless_from_env,
)
from mutiny_core.campaign.engine import CampaignResult
from mutiny_core.regress import RegressionNotReproducibleError
from mutiny_openai_agents.loader import ensure_project_on_path, load_adapter_factory

from mutiny_cli.hosted_sync import (
    SYNC_FAILED_EXIT,
    LocalRunBundle,
    sync_local_campaign,
)


@dataclass
class LocalRunOutcome:
    """Local campaign result used by plain run and Hosted sync."""

    exit_code: int
    campaign_id: str
    result: CampaignResult | None = None
    events: list[MutinyEvent] = field(default_factory=list)
    regression_id: str | None = None
    regression_path: str | None = None
    regression_artifact: dict[str, Any] | None = None
    minimize_body: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None


def run_campaign(
    *,
    project_root: Path,
    hosted_url: str | None = None,
    hosted: bool = False,
    no_hosted: bool = False,
    attestation: bool = True,
) -> int:
    """Run a campaign.

    Execution-mode contract (M-PR2 + M-PR8C):
    - Default: **local** Core + project adapter (no upload).
    - ``--hosted`` / ``--hosted-url``: **local** Core execution, then redacted
      end-of-run ingest sync to Hosted (not Hosted customer ``exec_module``).
    - ``mutiny.yaml`` / env Hosted URLs alone never select Hosted.
    - ``--no-hosted`` remains a compatibility alias for local (default).
    """
    root = project_root.resolve()
    ensure_project_on_path(root)

    if no_hosted and (hosted or hosted_url):
        print(
            "error: --no-hosted conflicts with --hosted / --hosted-url",
            file=sys.stderr,
        )
        return 2

    # Explicit Hosted intent: --hosted and/or --hosted-url on the CLI.
    # Config api_url alone is never enough.
    want_hosted = bool(hosted or hosted_url) and not no_hosted

    config = _load_mutiny_yaml(root / "mutiny.yaml")
    try:
        policy, policy_path = load_project_policy(root)
    except PolicyValidationError as exc:
        print(f"error: invalid project policy — {exc}", file=sys.stderr)
        return 2

    if not attestation:
        print(
            "error: authorization attestation required "
            "(authorized testing only — do not pass --no-attestation)",
            file=sys.stderr,
        )
        return 2

    hosted_cfg = dict(config.get("hosted") or {})
    if hosted_url:
        hosted_cfg["api_url"] = hosted_url
    api_url = (hosted_cfg.get("api_url") or "").rstrip("/")
    ui_url = (hosted_cfg.get("ui_url") or "http://127.0.0.1:3000").rstrip("/")

    print()
    print("Mutiny run — behavioral fuzz campaign")
    print(f"  project: {root}")
    print(
        f"  policy:  {policy_path.name} · v{policy.version} · "
        f"{policy.target} · {len(policy.rules)} rule(s)"
    )
    print(
        f"  search:  N={config.get('population_size', 8)} "
        f"Gmax={config.get('max_generations', 6)} "
        f"seed={config.get('rng_seed', 0)}"
    )
    print("  safety:  attestation ✓ · authorized testing only")
    if want_hosted:
        print("  Execution mode: local + Hosted sync")
        print(
            "  note: customer adapter runs locally; Hosted receives "
            "redacted ingest only (ADR-019 / M-PR8C)"
        )
    else:
        print("  Execution mode: local")
    print()

    if want_hosted:
        if not api_url:
            print(
                "error: Hosted selected but no api_url "
                "(set hosted.api_url in mutiny.yaml or pass --hosted-url)",
                file=sys.stderr,
            )
            return 2
        return _run_local_with_hosted_sync(
            root=root,
            config=config,
            policy=policy,
            api_url=api_url,
            ui_url=ui_url,
        )

    outcome = _run_local(root, config, policy)
    return outcome.exit_code


def _run_local_with_hosted_sync(
    *,
    root: Path,
    config: dict[str, Any],
    policy: PolicySet,
    api_url: str,
    ui_url: str,
) -> int:
    """Local Core campaign, then end-of-run Hosted ingest sync.

    Hosted availability is **not** a prerequisite for local execution.
    Sync failure after local success returns ``SYNC_FAILED_EXIT`` (3) and
    never silently pretends ``--hosted`` was not requested.
    """
    campaign_id = str(uuid.uuid4())
    print(f"→ Local campaign (Core + .mutiny/adapter.py) · campaign_id={campaign_id}")
    print(f"  Hosted sync target: {api_url} (end-of-run ingest)")
    print()

    outcome = _run_local(root, config, policy, campaign_id=campaign_id)

    if outcome.result is None:
        # Catastrophic local failure before a CampaignResult — still attempt
        # nothing useful to sync; treat as local failure.
        return outcome.exit_code

    bundle = LocalRunBundle(
        campaign_id=outcome.campaign_id,
        project_root=root,
        config=config,
        policy_version=policy.version,
        policy_target=policy.target,
        result=outcome.result,
        events=list(outcome.events),
        regression_id=outcome.regression_id,
        regression_path=outcome.regression_path,
        regression_artifact=outcome.regression_artifact,
        minimize_body=outcome.minimize_body,
        started_at=outcome.started_at,
        completed_at=outcome.completed_at,
    )

    print()
    print("→ Hosted sync (observe-only ingest) …")
    sync = sync_local_campaign(bundle, api_url=api_url, ui_url=ui_url)
    if sync.ok:
        print(f"✓ {sync.message}")
        print()
        return outcome.exit_code

    print(f"warning: Hosted synchronization failed — {sync.message}", file=sys.stderr)
    if sync.error_code:
        print(f"  sync_error: {sync.error_code}", file=sys.stderr)
    if sync.pending_path is not None:
        try:
            rel = sync.pending_path.relative_to(root)
        except ValueError:
            rel = sync.pending_path
        print(f"  pending: {rel} (retry is future work)", file=sys.stderr)
    print(
        "  note: local campaign result above remains authoritative "
        "(exit distinguishes sync failure)",
        file=sys.stderr,
    )
    print()
    if outcome.exit_code != 0:
        # Local failure takes precedence over sync failure.
        return outcome.exit_code
    return SYNC_FAILED_EXIT


def _run_local(
    root: Path,
    config: dict[str, Any],
    policy: PolicySet,
    *,
    campaign_id: str | None = None,
) -> LocalRunOutcome:
    cid = campaign_id or str(uuid.uuid4())
    started_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    factory = load_adapter_factory(root)
    adapter = factory()

    if campaign_id is None:
        print("→ Local campaign (Core + .mutiny/adapter.py)")
    core_cfg = CampaignConfig(
        population_size=int(config.get("population_size", 8)),
        max_generations=int(config.get("max_generations", 6)),
        elite_count=int(config.get("elite_count", 2)),
        max_turns=int(config.get("max_turns", 4)),
        stop_on_first_violation=bool(config.get("stop_on_first_violation", True)),
        wall_clock_seconds=config.get("wall_clock_seconds"),
    )
    seeds = None
    if config.get("use_boundary_seeds", True):
        seeds = default_policy_seeds(policy)

    llm = try_featherless_from_env()
    mutator = "featherless" if llm else "template"
    print(f"  mutator: {mutator}")

    collected: list[MutinyEvent] = []

    def on_event(ev: MutinyEvent) -> None:
        collected.append(ev)
        if ev.type == EventType.GENERATION_STARTED:
            print(f"  generation {ev.payload.get('generation')} …")
        elif ev.type == EventType.CANDIDATE_SCORED:
            fit = float(ev.payload.get("fitness") or 0.0)
            mark = " · VIOLATION" if ev.payload.get("violated") else ""
            print(
                f"    {ev.payload.get('candidate_id')}: fitness={fit:.3f}{mark}"
            )
        elif ev.type == EventType.VIOLATION_DETECTED:
            print("  ✓ violation detected")

    engine = CampaignEngine(
        adapter=adapter,
        policy_set=policy,
        config=core_cfg,
        seeds=seeds,
        on_event=on_event,
        rng_seed=int(config.get("rng_seed", 0)),
        mutator=MutationEngine(
            llm=llm,
            rng_seed=int(config.get("rng_seed", 0)),
            max_turns=core_cfg.max_turns,
        ),
    )
    result = engine.run()
    completed_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    print()
    print(
        f"✓ Local finished: status={result.status} reason={result.reason} "
        f"violated={result.violated} candidates={len(result.candidates)}"
    )

    regression_id: str | None = None
    regression_path: str | None = None
    regression_artifact: dict[str, Any] | None = None
    minimize_body: dict[str, Any] | None = None

    if result.violated and result.best is not None:
        saved = _maybe_minimize_and_save(
            root, adapter, policy, result, campaign_id=cid, events=collected
        )
        if saved is not None:
            regression_id, regression_path, regression_artifact, minimize_body = saved
    else:
        print("  No violation this run — try different rng_seed or more generations.")

    print()
    exit_code = 0 if result.status != "error" else 1
    return LocalRunOutcome(
        exit_code=exit_code,
        campaign_id=cid,
        result=result,
        events=collected,
        regression_id=regression_id,
        regression_path=regression_path,
        regression_artifact=regression_artifact,
        minimize_body=minimize_body,
        started_at=started_at,
        completed_at=completed_at,
    )


def _maybe_minimize_and_save(
    root: Path,
    adapter: Any,
    policy: PolicySet,
    result: Any,
    *,
    campaign_id: str,
    events: list[MutinyEvent],
) -> tuple[str, str, dict[str, Any], dict[str, Any]] | None:
    assert result.best is not None
    print("  minimizing exploit …")
    events.append(
        MutinyEvent(
            type=EventType.MINIMIZATION_STARTED,
            payload={
                "campaign_id": campaign_id,
                "candidate_id": result.best.genome.id,
            },
        )
    )
    rules = [h.rule_id for h in result.best.hits if h.violated] or [
        r.id for r in policy.rules
    ]
    minimized = minimize_genome(
        result.best.genome,
        adapter=adapter,
        policy_set=policy,
        target_rule_ids=rules,
        campaign_id=campaign_id,
        candidate_id=result.best.genome.id,
    )
    minimize_body = {
        "candidate_id": result.best.genome.id,
        "original_turn_count": minimized.original_turn_count,
        "minimized_turn_count": minimized.minimized_turn_count,
        "still_reproduces": minimized.still_reproduces,
        "target_rule_ids": list(minimized.target_rule_ids),
    }
    events.append(
        MutinyEvent(
            type=EventType.EXPLOIT_MINIMIZED,
            payload={
                "campaign_id": campaign_id,
                "candidate_id": result.best.genome.id,
                **minimize_body,
            },
        )
    )
    if not minimized.still_reproduces:
        print("  minimize did not re-verify; skipping regression save")
        return None
    try:
        artifact = save_regression(
            minimized,
            name="cli_discovered_violation",
            target=policy.target,
            policy_set=policy,
        )
    except RegressionNotReproducibleError as exc:
        print(f"  regression refused: {exc}")
        return None
    out_dir = root / ".mutiny" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{artifact.name}.json"
    artifact_dict = artifact.model_dump(mode="json")
    out_path.write_text(json.dumps(artifact_dict, indent=2), encoding="utf-8")
    print(f"  ✓ regression → {out_path.relative_to(root)}")
    print("  Next: fix the agent, then `mutiny test`")
    # Stable regression id for Hosted ingest (= local file stem).
    regression_id = out_path.stem
    events.append(
        MutinyEvent(
            type=EventType.REGRESSION_CREATED,
            payload={
                "campaign_id": campaign_id,
                "regression_id": regression_id,
                "candidate_id": result.best.genome.id,
                "path": str(out_path.relative_to(root)),
            },
        )
    )
    return (
        regression_id,
        str(out_path.relative_to(root)),
        artifact_dict,
        minimize_body,
    )


def _load_mutiny_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"error: missing {path}; run `mutiny init` first", file=sys.stderr)
        raise SystemExit(2)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"error: {path} must be a mapping")
    return data


def _load_policy(path: Path) -> PolicySet:
    """Load a single policy file (tests / helpers). Prefer ``load_project_policy``."""
    from mutiny_core import load_policy_file

    if not path.exists():
        print(f"error: missing {path}; run `mutiny init` first", file=sys.stderr)
        raise SystemExit(2)
    try:
        return load_policy_file(path)
    except PolicyValidationError as exc:
        print(f"error: invalid policy — {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
