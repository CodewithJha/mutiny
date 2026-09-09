"""``mutiny run`` — local Core by default; Hosted only when explicitly selected."""

from __future__ import annotations

import json
import sys
import time
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
from mutiny_core.regress import RegressionNotReproducibleError
from mutiny_openai_agents.loader import ensure_project_on_path, load_adapter_factory


def run_campaign(
    *,
    project_root: Path,
    hosted_url: str | None = None,
    hosted: bool = False,
    no_hosted: bool = False,
    attestation: bool = True,
) -> int:
    """Run a campaign.

    Execution-mode contract (M-PR2):
    - Default: **local** Core + project adapter.
    - Hosted only when explicitly selected via ``--hosted`` and/or ``--hosted-url``.
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
        print("  Execution mode: hosted")
        print(
        "  note: Hosted customer project_path adapter exec is disabled by "
        "default (M-PR1); a valid API token does not enable it"
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
        return _run_via_hosted(
            config=config,
            hosted_cfg=hosted_cfg,
            api_url=api_url,
            ui_url=ui_url,
            project_root=root,
            explicit=True,
        )

    return _run_local(root, config, policy)


def _run_via_hosted(
    *,
    config: dict[str, Any],
    hosted_cfg: dict[str, Any],
    api_url: str,
    ui_url: str,
    project_root: Path,
    explicit: bool = True,
) -> int:
    """Register + start Hosted campaign, poll to completion.

    When ``explicit`` is True (M-PR2 default for Hosted), failures return an
    error code and never fall back to local execution.
    """
    try:
        import httpx
    except ImportError:
        msg = "error: httpx missing — cannot reach Hosted API"
        if explicit:
            print(msg, file=sys.stderr)
            return 1
        print(f"⚠  {msg}; falling back to local.")
        print()
        return 1  # should not be called non-explicit anymore

    # Hosted loads policy.yaml from project_path (same file as local CLI).
    payload = {
        "population_size": int(config.get("population_size", 8)),
        "max_generations": int(config.get("max_generations", 6)),
        "elite_count": int(config.get("elite_count", 2)),
        "max_turns": int(config.get("max_turns", 4)),
        "stop_on_first_violation": bool(config.get("stop_on_first_violation", True)),
        "rng_seed": int(config.get("rng_seed", 0)),
        "target": "openai_agents",
        "project_path": str(project_root.resolve()),
        "use_boundary_seeds": bool(config.get("use_boundary_seeds", True)),
    }

    headers = _hosted_auth_headers()
    token_configured = bool(headers)

    try:
        with httpx.Client(base_url=api_url, timeout=10.0, headers=headers) as client:
            health = client.get("/api/health")
            if health.status_code >= 400:
                print(
                    f"error: Hosted health HTTP {health.status_code} at {api_url}",
                    file=sys.stderr,
                )
                return 1

            meta = client.get("/api/meta")
            if meta.status_code == 200:
                safety = (meta.json() or {}).get("safety") or {}
                if safety.get("auth_required") and not token_configured:
                    print(
                        "error: Hosted API requires authentication "
                        "(set MUTINY_API_TOKEN); refusing silent local fallback",
                        file=sys.stderr,
                    )
                    return 1

            print(f"→ Hosted API  {api_url}")
            print(f"  project     {project_root}")
            print("  adapter     .mutiny/adapter.py (loaded on server)")
            print("  policy      policy.yaml (loaded on server from project)")
            if token_configured:
                print("  auth        Authorization: Bearer <MUTINY_API_TOKEN>")
            created = client.post("/api/campaigns", json=payload)
            if created.status_code == 401:
                print(
                    "error: Hosted authentication failed "
                    "(set a valid MUTINY_API_TOKEN); refusing silent local fallback",
                    file=sys.stderr,
                )
                return 1
            if created.status_code >= 400:
                print(
                    f"error: Hosted create failed ({created.status_code}): "
                    f"{created.text[:200]}",
                    file=sys.stderr,
                )
                return 1
            body = created.json()
            campaign_id = body.get("id")
            if not campaign_id:
                print(
                    "error: Hosted create returned no campaign id",
                    file=sys.stderr,
                )
                return 1

            started = client.post(
                f"/api/campaigns/{campaign_id}/start",
                json={"attestation": True},
            )
            if started.status_code == 401:
                print(
                    "error: Hosted authentication failed "
                    "(set a valid MUTINY_API_TOKEN); refusing silent local fallback",
                    file=sys.stderr,
                )
                return 1
            if started.status_code >= 400:
                print(
                    f"error: Hosted start failed ({started.status_code}): "
                    f"{started.text[:300]}",
                    file=sys.stderr,
                )
                return 1

            dash = f"{ui_url}/campaign/{campaign_id}"
            print(f"  campaign    {campaign_id}")
            print(f"  dashboard   {dash}")
            print()
            print("Watching Hosted campaign (source of truth) …")

            final = _poll_campaign(client, campaign_id)
            status = final.get("status")
            metrics = final.get("metrics") or {}
            print()
            print(
                f"✓ Hosted finished: status={status} "
                f"violated={metrics.get('violated')} "
                f"candidates={metrics.get('candidates')} "
                f"elapsed_ms={metrics.get('elapsed_ms')}"
            )

            if status == "violation":
                _hosted_minimize_and_save(client, campaign_id)

            print()
            print("Open the dashboard for lineage + tool evidence:")
            print(f"  {dash}")
            print()
            return 0 if status != "failed" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"error: Hosted unreachable ({exc})", file=sys.stderr)
        return 1


def _hosted_auth_headers() -> dict[str, str]:
    """Bearer headers from ``MUTINY_API_TOKEN`` when set (never logged)."""
    import os

    raw = os.environ.get("MUTINY_API_TOKEN")
    if raw is None:
        return {}
    token = raw.strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}

def _poll_campaign(client: Any, campaign_id: str, timeout: float = 120.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_status = ""
    while time.time() < deadline:
        r = client.get(f"/api/campaigns/{campaign_id}")
        r.raise_for_status()
        body = r.json()
        status = body.get("status", "")
        if status != last_status:
            print(f"  … status={status}")
            last_status = status
        if status not in {"created", "running"}:
            return body
        # light candidate count
        c = client.get(f"/api/campaigns/{campaign_id}/candidates")
        if c.status_code == 200:
            n = len(c.json().get("candidates") or [])
            if n:
                print(f"  … candidates scored: {n}")
        time.sleep(0.35)
    raise TimeoutError(f"campaign {campaign_id} did not finish within {timeout}s")


def _hosted_minimize_and_save(client: Any, campaign_id: str) -> None:
    cands = client.get(f"/api/campaigns/{campaign_id}/candidates")
    if cands.status_code >= 400:
        return
    violators = [c for c in cands.json().get("candidates") or [] if c.get("violated")]
    if not violators:
        print("  (no violator row in Hosted candidates — open dashboard)")
        return
    vid = violators[0]["id"]
    print(f"  minimizing Hosted candidate {vid} …")
    m = client.post(f"/api/candidates/{vid}/minimize", json={})
    if m.status_code >= 400:
        print(f"  minimize failed: {m.status_code} {m.text[:160]}")
        return
    body = m.json()
    print(
        f"  minimize: turns {body.get('original_turn_count')} → "
        f"{body.get('minimized_turn_count')} · "
        f"still_reproduces={body.get('still_reproduces')}"
    )
    if not body.get("still_reproduces"):
        return
    s = client.post(
        f"/api/candidates/{vid}/regression",
        json={"name": "hosted_cli_violation"},
    )
    if s.status_code >= 400:
        print(f"  regression save failed: {s.status_code} {s.text[:160]}")
        return
    print(f"  ✓ regression saved: {s.json().get('id')}")
    print("  Next: Hosted /tests dashboard, or copy artifact into")
    print("        .mutiny/tests/ and run `mutiny test`")


def _run_local(root: Path, config: dict[str, Any], policy: PolicySet) -> int:
    factory = load_adapter_factory(root)
    adapter = factory()

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

    def on_event(ev: MutinyEvent) -> None:
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

    print()
    print(
        f"✓ Local finished: status={result.status} reason={result.reason} "
        f"violated={result.violated} candidates={len(result.candidates)}"
    )

    if result.violated and result.best is not None:
        _maybe_minimize_and_save(root, adapter, policy, result)
    else:
        print("  No violation this run — try different rng_seed or more generations.")

    print()
    return 0 if result.status != "error" else 1


def _maybe_minimize_and_save(
    root: Path, adapter: Any, policy: PolicySet, result: Any
) -> None:
    assert result.best is not None
    print("  minimizing exploit …")
    rules = [h.rule_id for h in result.best.hits if h.violated] or [
        r.id for r in policy.rules
    ]
    minimized = minimize_genome(
        result.best.genome,
        adapter=adapter,
        policy_set=policy,
        target_rule_ids=rules,
        campaign_id="cli-local",
        candidate_id=result.best.genome.id,
    )
    if not minimized.still_reproduces:
        print("  minimize did not re-verify; skipping regression save")
        return
    try:
        artifact = save_regression(
            minimized,
            name="cli_discovered_violation",
            target=policy.target,
            policy_set=policy,
        )
    except RegressionNotReproducibleError as exc:
        print(f"  regression refused: {exc}")
        return
    out_dir = root / ".mutiny" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{artifact.name}.json"
    out_path.write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    print(f"  ✓ regression → {out_path.relative_to(root)}")
    print("  Next: fix the agent, then `mutiny test`")


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
