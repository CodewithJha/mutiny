# Mutiny — Production Readiness Audit

| Field | Value |
|---|---|
| **Document** | Canonical production-readiness master plan |
| **Status** | Active — **documentation / architecture planning only** (no implementation in this revision) |
| **Audit date** | 2026-09-09 |
| **Repo version audited** | `v0.1.0` / `main` @ post-0.1.0 docs/CI commits |
| **Method** | Claims verified against current code under `packages/`, `apps/`, `tests/`, `.github/`, and canonical docs |
| **Hierarchy** | PRD → ARCHITECTURE → SYSTEM_DESIGN → IMPLEMENTATION_PLAN → DECISION_LOG → ROADMAP → **this doc (readiness gate)** |

**Related:** [ARCHITECTURE.md](./ARCHITECTURE.md) · [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) · [DECISION_LOG.md](./DECISION_LOG.md) · [ROADMAP.md](./ROADMAP.md) · [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) · [SECURITY.md](../SECURITY.md)

**Conflict rule:** Product intent → PRD. Hard boundaries → ARCHITECTURE. Runtime contracts → SYSTEM_DESIGN. Sequencing → IMPLEMENTATION_PLAN. Decisions → DECISION_LOG. **Ship / no-ship readiness and Hosted vs Local CLI gates → this document.** If an ADR conflicts with readiness findings, propose a superseding ADR — do not silently rewrite history.

---

## Executive Summary

Mutiny **v0.1.0** is a credible **alpha OSS behavioral fuzz engine**: Core oracle, Adapter #1 (OpenAI Agents SDK), CLI (`init` / `run` / `test`), sample project, and a local Hosted lineage UI/API. Unit tests are green (`126` passed in this audit). PyPI packages are published.

It is **not** production-ready as a **public or multi-tenant Hosted** service. With M-PR1, customer `project_path` adapter `exec_module` is **disabled by default**; with M-PR7, optional Bearer auth exists when `MUTINY_API_TOKEN` is set. Residual risk: opt-in `MUTINY_ALLOW_PROJECT_EXEC=1` still runs customer Python **in-process** (no path sandbox), attestation is not authorization, rate limits are missing, and deploy templates may bind `0.0.0.0`. That combination remains an **RCE / filesystem write** class risk if Hosted is reachable beyond a single trusted operator machine.

**Target A — Production Local CLI** is approachable with a focused hardening sequence (default local `mutiny run`, secret hygiene, policy-general seeds/mutators, CI completeness).

**Target B — Production Hosted** requires implementing **ADR-019 (accepted: observe-only Hosted)** via **M-PR8** (CLI executes customer agent; Hosted observes lineage) before any internet-facing claim. Until then, Hosted must be documented and operated as **localhost / single-operator demo only**.

---

## Current State

### What is shipped (verified)

| Surface | Evidence |
|---|---|
| Core kernel | `packages/mutiny_core` — policy, campaign, fitness, mutate, minimize, regress; no FastAPI/React/SQL |
| Adapter #1 | `packages/mutiny_openai_agents` — `OpenAIAgentsAdapter`, file loader for `.mutiny/adapter.py` |
| CLI | `packages/mutiny_cli` — `mutiny init` / `run` / `test`; PyPI name `mutiny-ai` @ `0.1.0` |
| Sample project | `examples/openai_support_agent/` with offline scripted model path |
| Hosted API | `apps/api` — campaigns, SSE, minimize, regressions, projects, policy CRUD |
| Hosted UI | `apps/web` — talks HTTP/SSE to API only (ADR-014) |
| Demo harness | `apps/demo_agent` — `in_process_demo` still supported by supervisor |
| CI | `.github/workflows/ci.yml` — unit + integration + reliability (3.11/3.12), CLI smoke, web build, package build |
| Publish | `.github/workflows/publish.yml` + `docs/PUBLISHING.md` |
| Tag | `v0.1.0` |

### What docs claim vs code (material drift)

| Claim | Reality |
|---|---|
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) marks M2–M5 largely **Planned/Partial** (2026-08-07) | Adapter #1 + CLI init/run/test + sample path are **shipped in 0.1.0** |
| ARCHITECTURE: API owns “rate limits” + “target allowlisting” | **No rate limiter** implemented; “allowlist” is a **target enum** (`in_process_demo` \| `openai_agents`), not a filesystem/URL sandbox |
| SYSTEM_DESIGN §20: arbitrary remote hosts blocked; treat customer adapter as untrusted vs control plane | **ADR-019** accepts observe-only Target B; **current code** still *can* `exec_module` customer adapters when `MUTINY_ALLOW_PROJECT_EXEC=1` (M-PR1 kill-switch default off). M-PR8 not implemented |
| PRD / plan: “Redact secrets in traces” | **M-PR3:** deterministic redaction on persist/display (`mutiny_core.redact`) |
| `docker-compose.yml` sets `MUTINY_DB_PATH` | **M-PR4:** `resolve_db_path()` honors env (compose `/app/data/mutiny.sqlite`); default remains `data/mutiny.sqlite` |
| ADR-001 “Hosted first” | Superseded for **product priority** by ADR-017; **M-PR2:** CLI default is local; Hosted requires `--hosted` / `--hosted-url` |

### Honest product posture today

- **Primary usable path:** developer machine → `pip install mutiny-ai` → `mutiny init` → `mutiny run` → `mutiny test`.
- **Hosted:** valuable **lineage/ops demo** on localhost; **not** a safe shared cloud control plane. CLI selects Hosted only via `--hosted` / `--hosted-url`.
- **MVP limitations (not bugs):** one adapter; three policy primitives; single concurrent campaign; SQLite; template/LLM mutation quality varies; refund demo remains the bundled sample (product seeds/mutators are policy-derived as of M-PR6).

---

## Production Definition

Two explicit targets. Do not collapse them.

### A. Production Local CLI

A release is **Production Local CLI ready** when a developer can, on their own machine, against an agent they are authorized to test:

1. Install `mutiny-ai` from PyPI without monorepo `uv sync`.
2. `mutiny init` scaffolds valid artifacts.
3. `mutiny run` completes a campaign using Core + Adapter #1 only (Hosted is opt-in via `--hosted`).
4. Violations are proven by deterministic policy evaluation on real tool traces (no LLM judge).
5. Minimize + save under `.mutiny/tests/`; `mutiny test` FAIL→PASS after a documented agent fix.
6. Secrets are not written plainly into artifacts by default (or are clearly warned + redacted).
7. Safety UX: authorized-use messaging; no silent dependency on a Hosted process.
8. CI covers unit + sample offline path; release notes match behavior.
9. Docs do not claim multi-framework or multi-tenant Hosted.

**Out of Local CLI production scope:** public Hosted API, multi-tenant auth, remote worker fleets, non-OpenAI adapters.

### B. Production Hosted

A release is **Production Hosted ready** when, in addition to Local CLI readiness:

1. Explicit **trust boundary** documented and enforced in code (see below).
2. **Authentication + authorization** on mutating and data-exfiltrating endpoints.
3. Customer agent code **does not execute inside the shared API process** (or runs only in a hardened per-tenant sandbox with a written threat model).
4. Filesystem access is scoped (no arbitrary `project_path` → host FS write/RCE).
5. Rate limits, concurrency caps, and abuse controls are real.
6. Persistence has backup/restore and migration discipline suitable for durable tenant data.
7. Deploy story (compose/Railway/etc.) does not contradict the threat model.
8. SECURITY.md and ops runbooks match the actual attack surface.

**Current Hosted does not meet this definition.** Treating checkbox attestation + localhost marketing as “production Hosted” is incorrect.

---

## Trust Boundaries

### Local CLI (Target A)

```
┌─────────────────────────────────────────────────────────┐
│ Developer machine (single trust domain)                 │
│  CLI ──► Core ──► load .mutiny/adapter.py ──► agent     │
│           │                                              │
│           └─► policy.yaml, .mutiny/tests/, optional LLM  │
└─────────────────────────────────────────────────────────┘
```

- **Trusted:** developer OS user, Core binary from PyPI, policy they wrote.
- **Untrusted relative to oracle:** model outputs, attack genomes (must not become instructions to Mutiny control logic).
- **Intentional:** executing the customer adapter in-process is **acceptable** for Local CLI — same trust as running `pytest` against their project.
- **Optional Hosted on same machine:** only safe if API is bound to loopback and the operator understands it shares the process/FS with whatever `project_path` is passed.

### Hosted (Target B) — required boundary

```
┌──────────────┐     authz      ┌──────────────────────────┐
│ Browser / CLI│ ─────────────► │ Hosted API (control)     │
└──────────────┘                │  - no customer exec      │
                                │  - persist lineage       │
                                └────────────┬─────────────┘
                                             │ events / artifacts only
                                ┌────────────▼─────────────┐
                                │ CLI-side execution       │
                                │ (ADR-019 Option A)       │
                                │  — M-PR8 not yet shipped │
                                └──────────────────────────┘
```

**Hard rule for Hosted production (ADR-019):** arbitrary customer Python **must not** run in the shared Hosted API process. **Verified today (pre-M-PR8):** without opt-in, M-PR1 refuses customer path; with `MUTINY_ALLOW_PROJECT_EXEC=1`, `CampaignSupervisor._make_adapter` → `load_adapter_factory` → `spec.loader.exec_module(mod)` still exists — localhost debt only.

**SYSTEM_DESIGN §20** already says treat customer adapter as untrusted vs the control plane. Current opt-in Hosted path **violates** that boundary; Target B fix is ADR-019 → M-PR8, not weakening the doc.

---

## Findings by Priority

Classification: **P0** security/data-loss/catastrophic · **P1** production blocker · **P2** significant debt · **P3** polish · **P4** future.  
MVP limitations are labeled as such, not “bugs.”

### P0 — Security / catastrophic

| ID | Finding | Evidence | Targets |
|---|---|---|---|
| P0-1 | **Unauthenticated Hosted API** — any client can create/start campaigns, read traces, write policies, delete regressions | `apps/api/src/mutiny_api/app.py` — no auth middleware/deps; SYSTEM_DESIGN §10 admits no multi-tenant auth | Hosted |
| P0-2 | **In-process RCE via `project_path`** — Hosted resolves arbitrary paths and `exec_module`s `.mutiny/adapter.py` | `resolve_project_root`, `load_adapter_factory`, `_make_adapter` | Hosted (fatal if network-exposed) |
| P0-3 | **Arbitrary policy file write** on server FS via `PUT /api/policies/content` after path resolve | `save_policy_content` in `app.py` | Hosted |
| P0-4 | **Public bind without auth** — Railway `0.0.0.0` + nixpacks start; compose publishes `8000:8000` | `railway.toml`, `docker-compose.yml` | Hosted |

### P1 — Production blockers

| ID | Finding | Evidence | Targets |
|---|---|---|---|
| P1-1 | Attestation is **not authorization** (boolean only) | `CampaignStartRequest.attestation`; supervisor `PermissionError` if false | Hosted (and weak Local messaging) |
| P1-2 | Docs/architecture claim **rate limits** and **path/URL allowlisting**; missing or reduced to target enum | ARCHITECTURE §4 API owns; no limiter in API; no FS root allowlist | Hosted |
| P1-3 | **Secret redaction** required by PRD — **implemented (M-PR3)** | `mutiny_core.redact`; persist/display wiring | Both (resolved for common patterns) |
| P1-4 | CLI **Hosted-first** when `api_url` reachable — surprises operators; pushes `project_path` to API | `run_cmd.py` | Local (ops safety); Hosted blast radius |
| P1-5 | `MUTINY_DB_PATH` in compose **ignored**; DB path hardcoded — **resolved (M-PR4)** | `mutiny_api.db.resolve_db_path` | Hosted / Data |
| P1-6 | CI runs **unit only** — integration + reliability not gated on PR — **resolved (M-PR5)** | `.github/workflows/ci.yml` | Both / OSS |
| P1-7 | [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) **stale** vs 0.1.0 — misleads maintainers on ship status | Milestone table vs CHANGELOG / code | OSS |

### P2 — Significant debt

| ID | Finding | Evidence |
|---|---|---|
| P2-1 | Campaign defaults to **refund-oriented seeds** when caller omits seeds — **resolved (M-PR6)** | `default_policy_seeds` via AttackFocus; `boundary_refund_seeds` harness-only |
| P2-2 | Template mutator + LLM prompts **hardcode** refund/`issue_refund`/`amount>200`/`ord_1001` — **resolved (M-PR6)** | Templates/prompts consume AttackFocus tools/thresholds/probes |
| P2-3 | Featherless concrete client lives in Core (port OK; **provider-named** surface in kernel package) | `mutiny_core/llm/featherless.py`, ADR-012 |
| P2-4 | `publish.yml` verify step **hardcodes `0.1.0`** — **resolved (M-PR5)**; reads each package `pyproject.toml` | Was fail/misleading on next version |
| P2-5 | Regressions table has **no `project_id`**; filtering joins via campaigns | `db.py` schema |
| P2-6 | No SQLite backup/export tooling for Hosted data | ops gap |
| P2-7 | Empty `integrations/` vs ARCHITECTURE diagram mentioning MCP/skills | placeholder only |
| P2-8 | No Dependabot/Renovate; no CODEOWNERS | OSS maintainer load |
| P2-9 | CLI help mentions `--no-attestation` in error text but **flag not defined** | `run_cmd.py` vs `main.py` |
| P2-10 | ARCHITECTURE “allowed targets localhost-only” not enforced for Hosted product path (FS paths, not HTTP) | constraint vs `resolve_project_root` |

### P3 — Polish

| ID | Finding |
|---|---|
| P3-1 | Demo pin / Iris narrative still prominent in Hosted meta (`demo_pin`, `iris-demo-pin`) |
| P3-2 | Default regression name `refund_limit_regression` |
| P3-3 | CONTRIBUTING/GOOD_FIRST_ISSUES strong; link this readiness doc from hub |
| P3-4 | Web a11y / copy still partially demo-centric in places |
| P3-5 | No Dockerfile (compose uses stock images + volume mount) |

### P4 — Future (not blockers; ROADMAP-aligned)

| ID | Finding |
|---|---|
| P4-1 | Additional framework adapters |
| P4-2 | Postgres, multi-campaign workers, org workspaces |
| P4-3 | MCP / Skills |
| P4-4 | Policy packs library, richer primitives |
| P4-5 | Authenticated single-tenant Hosted (ROADMAP v1) — requires ADR before coding |

---

## Architecture Risks

1. **Hosted execution model incompatible with untrusted tenants** — in-process adapter load is fine for Local CLI; fatal for shared Hosted. **ADR-019 accepted (Option A observe-only); M-PR8 not implemented.**
2. **Product narrative vs Hosted-first CLI** — ADR-017 says customer CLI primary; **M-PR2** aligns defaults (local; Hosted via `--hosted`).
3. **Search heuristics coupled to refund demo** — **resolved for defaults (M-PR6 / ADR-020)**; refund packs remain harness helpers.
4. **Single-process asyncio + SQLite** — acceptable for Local/demo Hosted; not multi-writer SaaS (ADR-005/007 already acknowledge). ADR-019 deliberately avoids Option B workers for Target B.
5. **Doc drift (IMPLEMENTATION_PLAN)** — planning hazard; can cause wrong prioritization.

---

## Security Model

### Current (as implemented)

| Control | Local CLI | Hosted today |
|---|---|---|
| AuthN | OS user | Optional Bearer (`MUTINY_API_TOKEN`, M-PR7); unset = open local demo |
| AuthZ | Operator discipline | Checkbox attestation (not identity) |
| Target isolation | Same process as developer agent | **Kill-switch (M-PR1):** customer adapter exec disabled by default; trusted `in_process_demo` only unless `MUTINY_ALLOW_PROJECT_EXEC=1`. **Target (ADR-019):** observe-only — **M-PR8 not implemented** |
| Network bind | N/A (CLI) | `0.0.0.0` in deploy templates |
| Rate limit | N/A | **Missing** (error code only) |
| Secret redaction | Pass (M-PR3) | Pass (M-PR3; Hosted persist/SSE) |
| Oracle integrity | Deterministic evaluator (strong) | Same (strong) |
| Open-internet attack proxy | Not implemented as product | Not a proxy; but **RCE on API host** is worse |

### Required model for Target B

1. AuthN (at least API token / session) on all non-health routes.
2. AuthZ: project ownership; no cross-tenant reads.
3. Execution: **ADR-019 accepted (Option A observe-only)** — implement via **M-PR8** (not yet). Isolate by relocating customer Python to CLI; do not claim workers unless a superseding ADR chooses Option B.
4. Filesystem: chroot/allowlisted roots or no server-side project paths.
5. Abuse: rate limits, campaign concurrency, payload size caps (ARCHITECTURE numbers → enforced).
6. Secrets: redact before persist/SSE; never log API keys.
7. Threat model doc updated in SECURITY.md when Hosted leaves localhost-only.

### Local CLI security bar (Target A)

- Document that adapter execution is intentional and equivalent to running project code.
- Default `mutiny run` should not silently escalate to Hosted on loopback without clear UX (**M-PR2:** local default; Hosted via `--hosted`).
- Redact common secret patterns in saved regressions/traces.
- Keep “authorized testing only” messaging; do not add open-internet target adapters without ADR.

---

## Modularity Audit

### Healthy (verified)

- Core does not import `apps.*` / demo FastAPI routes.
- OpenAI Agents SDK imports confined to `mutiny_openai_agents`.
- Web does not evaluate policies (HTTP client only).
- `TargetAdapter` port + `AttackFocus` derivation from policy tools/rules.
- Policy primitives are data-driven (`deny_tool` / `require_args` / `forbid_args`).

### Hardcoded / non-modular logic (verified instances)

| Location | What is hardcoded | Impact |
|---|---|---|
| `campaign/config.py` `boundary_refund_seeds` / `default_refund_seeds` | `ord_1001`, dollar amounts, `refund_limit` | **Demo/harness pack only** (ADR-020); Core default is `default_policy_seeds` |
| `fitness/__init__.py` | APR/manager cue strings | Mild; mostly generic |
| CLI `init` `POLICY_YAML` | Refund + delete templates | OK as **scaffold**, not engine hardcoding |
| API `schemas.RegressionSaveRequest` | Default name `refund_limit_regression` | UX bias (P3; out of M-PR6) |
| Supervisor `DEFAULT_SAMPLE_PROJECT` | `examples/openai_support_agent` | Fine for local Hosted default |

**Verdict:** Oracle is modular; **product seed/mutation targeting is policy-derived (M-PR6 / ADR-020)**. Refund corpora remain as bundled demo/example helpers, not Core defaults.

---

## Hosted Readiness

| Gate | Status |
|---|---|
| Lineage UX / SSE | Works locally |
| Core correctness via API | Works |
| AuthN/AuthZ | **Fail** |
| Safe customer code execution | **Fail** |
| FS sandbox | **Fail** |
| Rate limits | **Fail** |
| Durable multi-user data | **Fail** (SQLite + no backup story) |
| Internet deploy | **Unsafe** with current architecture |

**Operating rule until Target B milestones land:** Hosted = **localhost / single-operator only**. Do not market Railway/public URLs as production. Prefer leaving `MUTINY_ALLOW_PROJECT_EXEC` unset on any shared deploy (M-PR1). ADR-019 Target B = observe-only (M-PR8 not yet).

---

## CLI Readiness

| Gate | Status |
|---|---|
| `init` / `run` / `test` shipped | Pass |
| Offline sample path | Pass (`MUTINY_SAMPLE_OFFLINE`) |
| Local Core path (default) | Pass |
| Default Hosted-first | **Fixed (M-PR2)** |
| Attestation UX consistency | Pass (BooleanOptionalAction `--no-attestation`) |
| Domain-general seeds/mutators | Pass (M-PR6 / ADR-020) |
| Secret redaction | Pass (M-PR3) |
| PyPI install story | Pass (`mutiny-ai`) |

**Closest path to Target A:** local `mutiny run` is the production default (M-PR2); harden artifacts; generalize seeds/mutators; keep Hosted optional and opt-in via `--hosted`.

---

## Data / Persistence Readiness

| Topic | Status |
|---|---|
| SQLite WAL + migrations | Present (`SCHEMA_VERSION = "10"`) |
| Core free of SQL | Pass |
| Env-configurable DB path | **Broken** (P1-5) |
| Regressions linked to projects | Indirect via campaign only (P2-5) |
| Backup / restore | Missing (P2-6) |
| Trace size caps | Documented in ARCHITECTURE; enforcement incomplete at API edge |
| Local CLI artifacts | JSON under `.mutiny/tests/` — adequate for Target A |

---

## CI/CD Readiness

| Topic | Status |
|---|---|
| Unit tests on 3.11/3.12 | Pass (PR gate) |
| Integration tests in CI | **Pass** — offline `tests/integration` on PR (M-PR5) |
| Reliability smoke in CI | **Pass** — `tests/reliability` on PR (M-PR5) |
| CLI local smoke in CI | **Pass** — sample `mutiny init` + `mutiny run` (no Hosted) |
| Publish workflow | Present; verify reads package `pyproject.toml` versions (M-PR5) |
| Web typecheck + build in CI | Present (`apps/web`) |
| Package build in CI | Present (`mutiny-core` / `mutiny-openai-agents` / `mutiny-ai`) |
| Branch protection assumptions | Not verified in this audit (ops) |

---

## OSS Maintainer Readiness

| Asset | Status |
|---|---|
| LICENSE MIT, COC, SECURITY, SUPPORT, CONTRIBUTING | Present |
| Issue/PR templates, good-first-issues | Present |
| Docs hub | Present; must point here |
| IMPLEMENTATION_PLAN freshness | **Stale** (P1-7) |
| Dependabot / CODEOWNERS | Missing (P2-8) |
| Security disclosure path | Present |
| Honest non-goals | Mostly good; Hosted risk under-emphasized |

---

## Release Strategy

**Current:** `v0.1.0` (2026-08-09) — initial public promotion.

Do **not** blindly label next as `0.2.0` / `0.3.0` / `1.0.0` without tying versions to readiness gates.

| Version | Intent | Exit criteria (summary) |
|---|---|---|
| **0.1.x** | Alpha patch line | Docs/CI/safety messaging; no Hosted architecture rewrite required |
| **0.2.0** | **Production Local CLI** candidate | Target A DoD met; Hosted still localhost-only and labeled |
| **0.3.0** | Local CLI polish + Hosted **safe-mode** | Hosted cannot exec arbitrary `project_path` on shared deploys; auth token for non-loopback |
| **0.4.0+** | Hosted architecture per ADR-019 | Observe-only Hosted (CLI exec + ingest) — M-PR8 |
| **1.0.0** | Production Hosted + stable contracts | Target B DoD + stable public API/CLI contracts (ROADMAP v1 class) |

Patch releases (`0.2.1`, …) for fixes within a gate. Breaking Core/API contracts require minor bump pre-1.0 and ADR.

---

## Milestone Plan

**Protocol:** implement **one problem at a time** using the 13-step protocol in [Definition of Done](#definition-of-done). Never batch unrelated fixes.

Order is dependency-aware. Each milestone is independently testable.

### M-PR0 — Docs truth + Hosted danger labeling

| | |
|---|---|
| **Goal** | Align docs with reality; warn operators Hosted is localhost-only |
| **Problems solved** | P1-7; reduces accidental public exposure (process) |
| **Files** | `IMPLEMENTATION_PLAN.md`, `SECURITY.md`, `README` Hosted section, this doc |
| **Architecture impact** | None |
| **Dependencies** | None |
| **Tests** | Docs-only |
| **DoD** | Ship status table matches code; SECURITY states Hosted not internet-safe |
| **Rollback** | Revert docs commit |
| **Release** | 0.1.x |

### M-PR1 — Hosted kill-switch / loopback posture

| | |
|---|---|
| **Goal** | Prevent accidental RCE on shared deploys without full redesign |
| **Problems solved** | P0-2/P0-4 blast radius reduction |
| **Files** | `apps/api` config (e.g. refuse `openai_agents`+`project_path` unless `MUTINY_ALLOW_PROJECT_EXEC=1` and/or loopback-only bind docs) |
| **Architecture impact** | Temporary control; full fix is ADR-019 |
| **Dependencies** | M-PR0 |
| **Tests** | Integration: exec disabled by default in “hosted safe” mode |
| **DoD** | Default production-ish config cannot exec customer adapters |
| **Rollback** | Feature flag off |
| **Release** | 0.1.x or 0.2.0 |
| **Status** | **Implemented** — default deny; `MUTINY_ALLOW_PROJECT_EXEC=1` opt-in; trusted `in_process_demo` preserved |

### M-PR2 — Local CLI production default path

| | |
|---|---|
| **Goal** | `mutiny run` prefers local Core; Hosted opt-in |
| **Problems solved** | P1-4, P2-9 |
| **Files** | `mutiny_cli/run_cmd.py`, `main.py`, `CLI.md`, init `mutiny.yaml` defaults |
| **Architecture impact** | Aligns runtime with ADR-017 (product priority) |
| **Dependencies** | None (can parallel docs) |
| **Tests** | CLI unit tests for default local / opt-in hosted |
| **DoD** | Documented default matches ADR-017; Hosted requires explicit flag/url |
| **Rollback** | Revert CLI default |
| **Release** | 0.2.0 |
| **Status** | **Implemented** — default local; `--hosted` / `--hosted-url` opt-in; no silent Hosted fallback; `--no-hosted` kept as local alias |

### M-PR3 — Secret redaction in traces/artifacts

| | |
|---|---|
| **Goal** | Meet PRD secret redaction bar for Target A |
| **Problems solved** | P1-3 |
| **Files** | `mutiny_core` (pure redact helpers), CLI save path, API persist path |
| **Architecture impact** | None if pure function in Core |
| **Dependencies** | None |
| **Tests** | Unit: key-shaped strings redacted; regression golden |
| **DoD** | Saved artifacts and Hosted traces redact configured patterns |
| **Rollback** | Flag to disable (`MUTINY_DISABLE_SECRET_REDACTION=1`) or revert |
| **Release** | 0.2.0 |
| **Status** | **Implemented** — `mutiny_core.redact`; wired at campaign event dumps + SQLite/API evidence + CLI test evidence |

### M-PR4 — DB path + persistence hygiene

| | |
|---|---|
| **Goal** | Honor `MUTINY_DB_PATH`; document backup |
| **Problems solved** | P1-5, start P2-6 |
| **Files** | `mutiny_api/main.py`, compose docs |
| **Architecture impact** | None |
| **Dependencies** | None |
| **Tests** | Unit/integration with temp DB path env |
| **DoD** | Env controls DB location |
| **Rollback** | Revert main.py |
| **Release** | 0.2.0 |
| **Status** | **Implemented** — `resolve_db_path` (explicit → `MUTINY_DB_PATH` → `data/mutiny.sqlite`); fail-closed on invalid/empty path; parent dirs created; **backup/restore still a gap (P2-6)** |

### M-PR5 — CI completeness

| | |
|---|---|
| **Goal** | Gate PRs on unit + offline integration (and optional smoke) |
| **Problems solved** | P1-6; P2-4 |
| **Files** | `.github/workflows/ci.yml`, `.github/workflows/publish.yml` |
| **Architecture impact** | None |
| **Dependencies** | Stable offline sample |
| **Tests** | Workflow itself |
| **DoD** | `tests/integration` (offline) runs on PR; documented |
| **Rollback** | Revert workflow |
| **Release** | 0.2.0 |
| **Status** | **Implemented** — PR CI: `backend-tests` (unit+integration+reliability × 3.11/3.12), `cli-smoke` (local sample), `web-build`, `package-build`; publish verify uses `pyproject.toml` versions |

### M-PR6 — Policy-general seeds & mutators

| | |
|---|---|
| **Goal** | Remove refund-only hardcoding from Core search defaults |
| **Problems solved** | P2-1, P2-2 |
| **Files** | `campaign/config.py`, `campaign/engine.py`, `mutate/*` |
| **Architecture impact** | **ADR-020** accepted — policy-derived seeds/mutators |
| **Dependencies** | None beyond Core |
| **Tests** | Unit: non-refund policy gets non-refund seeds; mutator uses focus tools |
| **DoD** | Defaults derive from `PolicySet`/`AttackFocus`; refund templates only as examples — **done (M-PR6)** |
| **Rollback** | Callers may still pass `boundary_refund_seeds` / `default_refund_seeds` explicitly |
| **Release** | 0.2.0 |

### M-PR7 — Hosted authN (single-tenant token)

| | |
|---|---|
| **Goal** | Minimum auth before any non-loopback Hosted |
| **Problems solved** | P0-1, P1-1 (partial) |
| **Files** | `apps/api`, web middleware headers, CLI Hosted client, SECURITY.md |
| **Architecture impact** | **ADR-021** accepted — single-tenant Bearer token |
| **Dependencies** | M-PR1 |
| **Tests** | Integration: 401 without/invalid token; authenticated success; SSE; CLI; M-PR1 preserved |
| **DoD** | Protected routes require token when `MUTINY_API_TOKEN` is set — **done (M-PR7)** |
| **Rollback** | Unset `MUTINY_API_TOKEN` for local unauthenticated demo |
| **Release** | 0.3.0 |
| **Status** | **Implemented** — Bearer via `MUTINY_API_TOKEN`; public health/meta; auth does not bypass M-PR1 |

### M-PR8 — ADR-019 implementation (Hosted observe-only)

| | |
|---|---|
| **Goal** | Customer Python never in shared API process; Hosted ingests lineage from CLI |
| **Problems solved** | P0-2, P0-3 (re-shaped), Target B foundation |
| **Files** | API supervisor contracts, CLI event/artifact upload, possibly Web “Run” UX |
| **Architecture impact** | **ADR-019 accepted (Option A)** — implement observe-only; workers (Option B) rejected for now |
| **Dependencies** | ADR-019 accepted; M-PR1/M-PR7 |
| **Tests** | Contract tests: API without customer `exec_module`; CLI → Hosted ingest path |
| **DoD** | Threat model satisfied for single-tenant observe-only Hosted |
| **Rollback** | Safe-mode only Hosted (M-PR1) |
| **Release** | 0.4.0 → leads to 1.0.0 |
| **Status** | **Not implemented** — decision only in this docs revision |

### Later (P3/P4) — packaging verify fix, Dependabot, project_id on regressions, adapters, Postgres

Scheduled after Target A gate; do not block 0.2.0.

---

## Definition of Done

### Measurable — Production Local CLI (Target A)

- [ ] `pip install mutiny-ai==<ver>` on clean venv; `mutiny --help` works  
- [ ] Sample: `mutiny run` finds or honestly reports no violation without crashing  
- [ ] Regression save + `mutiny test` FAIL→PASS path documented and tested offline  
- [ ] No Hosted required for primary path; Hosted explicitly opt-in  
- [x] Secret redaction tests green  
- [x] Seeds/mutators policy-general (M-PR6 / ADR-020); refund packs remain demo/harness helpers 
- [x] CI: unit + offline integration green on PR  
- [ ] README/SECURITY/IMPLEMENTATION_PLAN match code  
- [ ] Version **≥ 0.2.0** tagged with CHANGELOG  

### Measurable — Production Hosted (Target B)

- [ ] All Target A checks  
- [ ] AuthN on mutating routes when `MUTINY_API_TOKEN` set (M-PR7) 
- [ ] No customer `exec_module` in API process for Production Hosted (ADR-019 → **M-PR8 not yet**)  
- [ ] Rate limits enforced  
- [ ] DB path configurable; backup procedure documented  
- [ ] Threat model in SECURITY.md; no public demo without auth  
- [ ] Version **1.0.0** (or explicit 0.4+ “Hosted beta” with same technical bar, labeled beta)  

### Future implementation protocol (ONE problem at a time)

**Never batch unrelated fixes.** For each milestone / finding:

1. **Select** exactly one problem ID (e.g. `P1-5`) or milestone (`M-PR4`).  
2. **Re-read** this doc + linked ADR/ARCHITECTURE constraints.  
3. **Write** a failing test or minimal repro (unless docs-only).  
4. **Implement** the smallest change that makes the test pass.  
5. **Avoid** drive-by refactors and unrelated files.  
6. **Update** docs only if contracts/claims change — never to hide a bug.  
7. **Open/adjust ADR** if the change alters an accepted decision.  
8. **Run** targeted tests for the change.  
9. **Run** `uv run pytest tests/unit -q` (and integration if touched).  
10. **Commit** one focused commit (message explains *why*).  
11. **Record** status against the milestone DoD in this file or IMPLEMENTATION_PLAN.  
12. **Stop** and wait for review/approval before starting the next problem.  
13. **Do not** start the next P0/P1 until the current one’s DoD is checked.

---

## Open Questions

1. Should **0.2.0** flip CLI default to local-only, or keep Hosted-first with louder warnings? → **Decided (M-PR2):** local default; Hosted via `--hosted` / `--hosted-url`.  
2. Preferred Target B shape: **(a)** observe-only Hosted (CLI runs agent), **(b)** per-job containers, **(c)** WASM/other sandbox? → **Decided (ADR-019):** **(a)** observe-only; M-PR8 implements; Option B deferred pending superseding ADR.  
3. Is single shared API token enough for “authenticated single-tenant,” or is user/session required for 1.0? → **Near-term (ADR-021 / M-PR7):** shared Bearer token; multi-user later.  
4. How long may refund-biased seeds remain if documented as known limitation for 0.2.0? → **Defaults generalized (M-PR6 / ADR-020)**; refund packs = harness helpers.  
5. Should Railway config be removed or hard-gated until M-PR1?  
6. Who owns Hosted vs CLI release trains (same version vs separate)?  

---

## Deferred Work

- LangGraph / CrewAI / PydanticAI / AutoGen / HTTP adapters (ROADMAP Beta)  
- MCP / Skills  
- Postgres / K8s / worker queues  
- Multi-tenant org model / SSO  
- Vector attack memory / LLM-as-judge acceptance  
- Web CI, visual regression, Dependabot (after Target A)  
- Full policy language expansion beyond three primitives  

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Public Hosted RCE via adapter load | Med if deployed | Critical | M-PR0/1; ADR-019; no public deploy |
| Operators trust attestation as security | High | High | Docs + auth milestone |
| Doc drift causes wrong roadmap work | High | Med | Refresh IMPLEMENTATION_PLAN; this doc as gate |
| Refund hardcoding → false “engine doesn’t work” on other tools | Med | Med | M-PR6 |
| Secret leakage in SQLite/SSE | Med | High | M-PR3 |
| Publish workflow breaks on next version | High | Low | Fix verify step with dynamic version |
| Concurrent campaigns / SQLite corruption under abuse | Low locally / Med exposed | Med | Concurrency=1 already; auth + limits |

---

## ADR Proposals (do not implement here)

### ADR-019 — Hosted must not execute customer Python in-process

**Status:** **Accepted** — see DECISION_LOG ADR-019 (Option A: observe/lineage Hosted; CLI executes customer adapters). **M-PR8 not implemented** in this revision.

**Current code (interim):** Hosted can still load `.mutiny/adapter.py` via `load_adapter_factory` when `MUTINY_ALLOW_PROJECT_EXEC=1` (M-PR1). Default remains refuse. Trusted `in_process_demo` harness unchanged.

**Why Target B needs M-PR8:** Even with auth (ADR-021), in-process customer `exec_module` + `project_path` remains RCE/FS-write risk and conflicts with SYSTEM_DESIGN §20.

**Options evaluated (decision locked):**

| Option | Idea | Outcome |
|---|---|---|
| **A** | Hosted observe/lineage; CLI executes adapter; uploads events/artifacts | **Accepted** |
| **B** | Ephemeral per-campaign worker (container/VM) | Rejected for now (ops + ADR-007); reconsider via new ADR |
| **C** | Hosted = `in_process_demo` forever; customer projects CLI-only | Rejected as permanent product shape; M-PR1 already approximates as interim |

**Migration (planned for M-PR8):** Keep M-PR1 fail-closed → ship CLI→Hosted ingest / redesign Hosted Run → remove production in-process customer path → update §12 diagrams to observe-only primary.

### ADR-020 — Policy-derived seeds/mutators (supersede refund defaults as engine core)

**Status:** **Accepted and implemented (M-PR6)** — see DECISION_LOG ADR-020.

**Current decision:** Demo reliability may still pin refund boundary seeds (ADR-016); Core campaign defaults to `default_policy_seeds` from `AttackFocus`.

**Why it failed for general production CLI:** Non-refund policies still searched refund conversations; LLM prompts encoded `amount > 200` / `issue_refund`.

**Replacement:** Default seeds/mutators derive from `AttackFocus` + policy constraints; keep refund corpora as **example pack** / demo pin helper only.

**Alternatives:** Per-domain seed packs selected by policy `target` field; user-supplied seed files in `mutiny.yaml`.

**Tradeoffs:** Slightly weaker out-of-box demo hit rate vs template smoke unless harness keeps refund pack explicitly (`boundary_refund_seeds`).

**Migration:** `default_policy_seeds(policy)` → engine/CLI/API default → leave `boundary_refund_seeds` as named helper for harness.

### Note on ADR-001 vs ADR-017

ADR-017 already supersedes ADR-001 for **product priority**. **M-PR2** aligns runtime CLI defaults with ADR-017 (local default; Hosted explicit). **ADR-019** further locks Hosted out of customer Python execution for Target B.

---

## Final Report (parent handoff)

### Current Production Readiness (scores 0–10)

| Dimension | Score | Notes |
|---|---|---|
| **Local CLI** | **8.5** | Default local path (M-PR2); common-secret redaction (M-PR3); policy-general seeds/mutators (M-PR6) |
| **Hosted** | **3.0** | Local demo only; M-PR1 kill-switch + optional M-PR7 auth; ADR-019 accepted but **M-PR8 not implemented** (opt-in in-process exec still exists) |
| **Core** | **8.0** | Strong oracle & package boundaries; search heuristics policy-derived (M-PR6) |
| **OSS** | **7.5** | Strong community files; PR CI covers unit/integration/reliability + smoke (M-PR5); stale implementation plan |
| **Packaging** | **8.5** | PyPI 0.1.0 real; publish verify reads package metadata (M-PR5) |
| **Security** | **4.0** | Oracle trustworthy; M-PR3 redaction; M-PR7 optional auth; Hosted still not Production Hosted (ADR-019 pending M-PR8) |
| **Overall** | **4.5** | Alpha suitable for authorized local fuzzing; not dual-target production |

### Critical Findings (P0/P1)

- **P0:** Unauthenticated Hosted + in-process adapter exec + policy write + public bind templates.  
- **P1:** Fake authz (attestation), missing rate limits/allowlist vs docs, stale IMPLEMENTATION_PLAN. *(P1-3 secret redaction resolved by M-PR3; P1-4 CLI Hosted-first resolved by M-PR2; P1-5 `MUTINY_DB_PATH` resolved by M-PR4; P1-6 CI completeness resolved by M-PR5.)*

### Architectural Findings (ADR needed)

- **ADR-019 (accepted, Option A):** Hosted observe/lineage; CLI executes customer Python — **M-PR8 implements (not done)**.  
- **ADR-020 (accepted, M-PR6):** Policy-general seeds/mutators.  
- **ADR-021 (accepted, M-PR7):** Single-tenant Bearer token.  
- Align CLI defaults with **ADR-017** (done via M-PR2).

### Hardcoded / Non-Modular Logic (verified instances)

- Refund seed helpers remain as demo/harness packs; Core/CLI/API defaults use `default_policy_seeds` — see Modularity Audit table.

### Documentation Conflicts

- IMPLEMENTATION_PLAN milestone status vs 0.1.0 ship.  
- ARCHITECTURE rate limits / allowlisting vs code.  
- SYSTEM_DESIGN trust boundary vs Hosted exec.  
- ADR-001 historical vs ADR-017 + CLI Hosted-first behavior.  
- PRD secret redaction — **addressed by M-PR3** (deterministic common-pattern redactor; not universal detection).  
- compose `MUTINY_DB_PATH` vs hardcoded DB path — **addressed by M-PR4**.

### Proposed Milestones (exact order)

1. M-PR0 Docs truth + danger labeling  
2. M-PR1 Hosted kill-switch / loopback posture  
3. M-PR2 Local CLI default path  
4. M-PR3 Secret redaction  
5. M-PR4 DB path hygiene  
6. M-PR5 CI completeness  
7. M-PR6 Policy-general seeds/mutators (ADR-020)  
8. M-PR7 Hosted authN token  
9. M-PR8 ADR-019 Hosted execution model  

Then P3/P4 items; **1.0.0** only after Target B DoD.

### Release Plan

`0.1.x` (safety docs/flags) → `0.2.0` (Production Local CLI) → `0.3.0` (Hosted safe-mode + auth) → `0.4.0` (ADR-019) → `1.0.0` (Production Hosted + stable contracts).

### Definition of Production Ready (measurable)

See checklists under [Definition of Done](#definition-of-done) for Target A and Target B separately.

### Documents Changed

- **Created:** `docs/PRODUCTION_READINESS.md` (this file)  
- **Updated for consistency pointers / ADR proposals / stale-status notes:** `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DECISION_LOG.md`, `docs/IMPLEMENTATION_PLAN.md`, `SECURITY.md`  
- **ADR-019 acceptance (docs-only):** `docs/DECISION_LOG.md`, `docs/ARCHITECTURE.md`, `docs/SYSTEM_DESIGN.md`, `docs/ROADMAP.md`, `docs/PRODUCTION_READINESS.md`, `SECURITY.md` — **M-PR8 not implemented**

**STOP:** No application or test code changes in this ADR-019 workstream. Implementation waits for explicit M-PR8 approval.
