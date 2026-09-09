# Mutiny — Architecture Decision Records

| Field | Value |
|---|---|
| **Status** | Canonical decision log |
| **Last updated** | 2026-09-09 |
| **Format** | ADR: Problem → Decision → Alternatives → Tradeoffs → Reconsider when |

Add new ADRs at the bottom. Do not rewrite history; supersede with a new ADR.

---

## ADR-001 — Hosted first, integrations second

**Problem:** Dual “Hosted Mutiny” and “Local Mutiny” products invite two architectures and dilute the demo.

**Decision:** One Core. **Hosted Mutiny** (API + web) is the primary product. CLI / Skills / MCP are secondary clients.

**Alternatives:** Local-CLI-first; dual peer products; MCP-first.

**Tradeoffs:** Stronger demo narrative; CLI slightly delayed. Risk of under-serving CI until P1.

**Reconsider when:** Hosted loop is reliable and CI demand blocks adoption.

---

## ADR-002 — Single shared Core package

**Problem:** UI and CLI can drift into divergent evaluation logic.

**Decision:** All policy, fitness, campaign, mutate, minimize, regress logic lives in `packages/mutiny_core`.

**Alternatives:** Duplicate logic per app; monorepo without package boundary.

**Tradeoffs:** Requires discipline on ports/interfaces; slightly more wiring.

**Reconsider when:** Core becomes large enough to split *within* domain modules—not across apps.

---

## ADR-003 — Deterministic policy oracle; no LLM judge for acceptance

**Problem:** LLM judges are flaky, costly, and weak as CI ground truth for tool arguments.

**Decision:** Violation acceptance is deterministic over tool traces. LLMs only propose/mutate text (and optional non-authoritative explanations).

**Alternatives:** LLM-as-judge primary; hybrid judge with deterministic secondary.

**Tradeoffs:** Less coverage for fuzzy semantic policies; sharper trust and testability.

**Reconsider when:** Supporting policies that cannot be expressed over tool args/context—and even then keep judges non-blocking for “hard fail” CI gates.

---

## ADR-004 — Evolutionary search over static jailbreak lists

**Problem:** Static lists do not aim at user-specific tool boundaries.

**Decision:** Generational population search with policy-conditioned mutation and fitness heuristics.

**Alternatives:** Fixed Promptfoo-style case generation only; pure human red team; random fuzz only.

**Tradeoffs:** Longer runtime; demo flake risk; needs engineered vulnerable target for reliability.

**Reconsider when:** Search consistently fails to beat strong seeded baselines for real targets.

---

## ADR-005 — SQLite for MVP persistence

**Problem:** Need durable campaigns/traces without ops burden.

**Decision:** SQLite via Hosted API repositories.

**Alternatives:** Postgres; in-memory only; file JSON store.

**Tradeoffs:** Simple deploy; limited write concurrency.

**Reconsider when:** Multi-writer Hosted deploy or team concurrency requires Postgres (see ROADMAP).

---

## ADR-006 — No vector database / no RAG memory

**Problem:** Temptation to store “attack embeddings” without clear MVP need.

**Decision:** No vector DB. Lineage is explicit parent pointers + traces.

**Alternatives:** Embedding-based seed retrieval; RAG over prior exploits.

**Tradeoffs:** Less automated reuse of historical attacks; far less infra complexity.

**Reconsider when:** Large exploit corpora make retrieval empirically necessary.

---

## ADR-007 — No Kubernetes / no queue workers for MVP

**Problem:** Distributed aesthetics burn hackathon time.

**Decision:** Single-process asyncio campaign execution; optional docker-compose for local Hosted.

**Alternatives:** Celery/Redis workers; K8s jobs.

**Tradeoffs:** Limited scale; excellent debuggability.

**Reconsider when:** Real multi-tenant Hosted load requires isolation/scale.

---

## ADR-008 — Monorepo

**Problem:** Split repos slow iteration across Core/API/Web/demo.

**Decision:** Single repository with `packages/`, `apps/`, `integrations/`.

**Alternatives:** Polyrepo; separate UI repo.

**Tradeoffs:** Clear boundaries needed to avoid spaghetti; simpler Iris workflow.

**Reconsider when:** Independent release cadences demand package publishing.

---

## ADR-009 — In-process demo adapter first; localhost HTTP later

**Problem:** Remote adapters add SSRF/auth complexity before the loop works.

**Decision:** MVP target is in-process demo agent; optional localhost HTTP is P2.

**Alternatives:** HTTP-only from day one; cloud targets.

**Tradeoffs:** Fastest path to real tool traces; weaker “bring your own endpoint” story until later.

**Reconsider when:** Core+Hosted violation loop is reliable.

---

## ADR-010 — Delta debugging with mandatory re-execution

**Problem:** LLM “shorten this exploit” lies.

**Decision:** Classical ddmin (then optional AI shorten) with re-exec + deterministic eval gate before save.

**Alternatives:** AI-only minimization; save full conversations only.

**Tradeoffs:** Extra target calls; high credibility.

**Reconsider when:** Never drop the re-exec gate; only change search heuristics inside minimize.

---

## ADR-011 — Small policy primitive set

**Problem:** Full policy languages (OPA/Cedar) explode scope.

**Decision:** MVP implements `deny_tool`, `require_args`, `forbid_args` only.

**Alternatives:** Embed Rego; free-form NL policies judged by LLM.

**Tradeoffs:** Limited expressiveness; implementable and testable.

**Reconsider when:** Real users hit expressiveness walls after MVP.

---

## ADR-012 — Featherless as primary model transport (Iris)

**Problem:** Need OpenAI-compatible inference aligned with Iris sponsorship.

**Decision:** OpenAI SDK against Featherless base URL for target + mutation models; Ollama/templates fallback.

**Alternatives:** OpenAI only; local-only models.

**Tradeoffs:** Sponsor fit; model catalog churn requires pinning.

**Reconsider when:** Provider reliability or tool-calling quality forces a pin change (update config, not architecture).

---

## ADR-013 — Single concurrent campaign hard limit

**Problem:** Parallel campaigns exhaust model concurrency and confuse demos.

**Decision:** Max concurrent campaigns = 1 per process (ARCHITECTURE constraints).

**Alternatives:** Unbounded; worker pool.

**Tradeoffs:** Simpler UX and resource control.

**Reconsider when:** Multi-user Hosted beta.

---

## ADR-014 — Web talks to API only

**Problem:** Importing Core into Next.js invites duplicate runtimes and leaked secrets.

**Decision:** `apps/web` uses HTTP/SSE to `apps/api` only.

**Alternatives:** Server components calling Core in-process.

**Tradeoffs:** Extra hop; clean trust boundary.

**Reconsider when:** A tightly coupled server-rendered deploy intentionally co-locates API+web with clear secret handling—still keep policy eval off the browser.

---

## ADR-015 — Inngest-inspired Hosted visual language

**Problem:** Hosted UI needed a coherent developer-tool aesthetic for Persuade (landing) and Operate (campaign/exploit/policies/tests) without inventing a one-off brand system mid-hackathon.

**Decision:** Pin [Inngest](https://www.inngest.com) v1 as visual canon for Mutiny Hosted — charcoal canvas (`#1c1c1c`), frost primary CTAs that hover to salmon (`#fb5536`), uppercase outline display headlines, floating salmon micro-dots, mono ■ code accordion. CircularXX is licensed to Inngest only; Mutiny uses Plus Jakarta Sans + IBM Plex Mono as stand-ins. Documented in root `DESIGN.md` / `PRODUCT.md`.

**Alternatives:** Teal-accent “developer dark” approximation; cream/editorial prototype; inventing a unique Mutiny brand from scratch.

**Tradeoffs:** Category-adjacent look (intentional); cannot ship CircularXX/Whyte without a license.

**Reconsider when:** Dedicated brand pass or licensed typefaces post-hackathon.

---

## ADR-016 — Demo pin + template smoke gate (M8)

**Problem:** Iris reliability needs a reproducible ≥2/3 smoke budget without depending on live Featherless availability.

**Decision:** Pin Hosted demo defaults in `config/demo_pin.json`. Reliability gate (`scripts/smoke_reliability.py`) runs three seeded campaigns with boundary seeds + template mutator fallback and requires ≥2/3 `refund_limit` violations with real `issue_refund` tool evidence. Backup nuclear path is fixture oracle + regression FAIL→PASS (`scripts/backup_fixture_demo.py`), not fabricated DB rows. Competitive claims remain frozen to COMPETITOR_ANALYSIS.

**Alternatives:** Require live LLM for smoke; skip smoke and rely on recording only.

**Tradeoffs:** Template search is weaker than LLM mutation for exploration, but is offline-deterministic for the demo agent harness.

**Reconsider when:** A pinned Featherless model is proven ≥2/3 live and becomes the default smoke path (update pin, keep template as fallback).

---

## ADR-017 — Customer-owned local projects primary; bundled demo secondary

**Problem:** The hackathon MVP centered product narrative and primary use case on a bundled vulnerable demo agent (Hosted Mutiny → in-process demo). That taught the Core loop but mis-positioned Mutiny as “a hosted demo agent product” rather than a tool developers install into **their own** agent projects. Continuing would widen the docs/code story around the wrong user flow and invite framework sprawl without an install path.

**Decision:**

1. **Primary product path:** Developer owns an OpenAI Agents SDK project → `pip install mutiny-ai` → `mutiny init` (`.mutiny/adapter.py`, `policy.yaml`, `mutiny.yaml`) → connect agent → `mutiny run` → campaign → minimize → regression tests.  
2. **Framework lock (current scope):** OpenAI Agents SDK **only**. LangGraph, CrewAI, PydanticAI, AutoGen, MCP, HTTP adapters = ROADMAP (Beta/v1).  
3. **Bundled demo agent:** Reclassified as **reference implementation / sample project / docs example / reliability harness** — not the primary user workflow.  
4. **Architecture preserved:** One Core; `TargetAdapter` port; Hosted API/UI remain valuable secondary surfaces for lineage/ops.  
5. **Supersedes (product priority only):** ADR-001’s “Hosted first” *product* primacy and ADR-009’s “in-process demo first” *as the product story*. Those ADRs remain historically valid for how the interim codebase was built; new work prioritizes customer-project + OpenAI Agents SDK adapter. Do not delete prior ADRs.

**Alternatives:** Keep demo-as-primary and add “BYO agent” later; CLI-only with no Hosted; multi-framework initial ship.

**Tradeoffs:** Docs and demo script now lead the intended install path while code may still wire the demo harness until M2–M4 land — requires honest DoD labeling. Stronger long-term product fit; short-term gap between narrative and shipped CLI/adapter surfaces.

**Reconsider when:** OpenAI Agents SDK adapter + `mutiny init`/`run` are reliable; if Hosted-attached remote targets become the dominant adoption path; or if a second framework is required for a concrete design partner (promote via ROADMAP + new ADR).

---

## ADR-018 — Adapter-first architecture

**Problem:** Product and docs risk defining Mutiny as “an OpenAI Agents SDK testing tool,” collapsing the engine with its first integration. That would (a) mis-sell the product, (b) invite Core contamination with framework-specific types and control flow, and (c) make every future framework look like a rewrite instead of a plug-in.

**Decision:**

1. **Product hierarchy (never reverse):** Mutiny → behavioral fuzz-testing engine → Adapter Layer → OpenAI Agents SDK (Adapter #1) → future adapters (LangGraph, PydanticAI, CrewAI, AutoGen, HTTP, etc.) → customer project.  
2. **Core is framework-independent:** campaign, policy, fitness, minimize, and regression stay free of OpenAI (or any framework) leakage. Adapter interfaces (`TargetAdapter`, `AdapterTurnResult`, ports) are framework-neutral.  
3. **Current scope ships one production-quality adapter:** OpenAI Agents SDK = Adapter #1. That is the first integration, not the product definition.  
4. **Future frameworks = more adapters:** add implementations on the same interface; Core unchanged.  
5. **Complements ADR-017:** customer-owned projects remain primary; this ADR locks the *engine vs adapter* positioning and Core boundary.

**Alternatives:** Hard-wire Core to OpenAI Agents SDK for speed; dual engines per framework; delay any adapter abstraction until later.

**Tradeoffs:** Slightly more abstraction and packaging work for Adapter #1 vs a direct SDK embed. Prevents positioning drift and Core rewrites when Beta adapters land. Docs must consistently say “engine + first adapter,” not “SDK tool.”

**Reconsider when:** A concrete design partner requires a second adapter before Adapter #1 is green (still add adapter, do not fork Core); or if the `TargetAdapter` contract proves insufficient for a major framework (extend the port via ADR—do not move framework logic into campaign/policy).

---

## ADR-020 — Policy-derived seeds and mutators (M-PR6)

**Problem:** Core campaign defaults and mutation templates/prompts were coupled to the refund demo (`issue_refund`, `ord_1001`, `amount > 200`). Non-refund policies still searched refund conversations, undermining the product thesis that `PolicySet → AttackFocus →` adversarial search.

**Decision:**

1. **Product default seeds** are `default_policy_seeds(policy_set)`, derived deterministically from `AttackFocus` (tools, rule ids, kinds, critical args, numeric thresholds, equality probes).  
2. **Mutation operators** stay strategy-level (rephrase, authority, APR bypass, argument nudge, …); templates and LLM prompts consume `AttackFocus` instead of refund-specific prose. Policy info chooses *what* to probe — it is not dumped as “please violate this rule” text to the target agent.  
3. **`boundary_refund_seeds` / `default_refund_seeds`** remain named **demo/harness helpers** (ADR-016 reliability, explicit caller opt-in). They are not the Core/CLI/API default.  
4. **Acceptance model unchanged:** deterministic `PolicyEvaluator` remains authoritative; no LLM judges.

**Alternatives:** Per-domain seed packs keyed by `target`; user-supplied seed files only; keep refund defaults with docs disclaimer.

**Tradeoffs:** Out-of-box refund demo hit rate may rely on harness-pinned boundary seeds for the offline smoke gate; general policies get relevant search without a second engine.

**Reconsider when:** Search quality on diverse policies needs richer constraint-aware generators or optional user seed corpora in `mutiny.yaml`.

---

## ADR-021 — Single-tenant Hosted API token (M-PR7)

**Problem:** Hosted API previously accepted unauthenticated control-plane calls (campaigns, policies, regressions, SSE). Attestation is a product safety checkbox, not identity. Multi-tenant OAuth/users/sessions are out of current scope and would expand the product surface without fixing the immediate exposure.

**Decision:**

1. **One shared server credential:** `MUTINY_API_TOKEN` environment variable. Clients send `Authorization: Bearer <token>`.
2. **Fail closed when enabled:** If the env var is set to a non-empty value, all protected `/api/*` routes reject missing/invalid credentials with the same `401 unauthorized` body (constant-time compare; no token echo).
3. **Local demo rollback:** If unset/empty, auth is disabled (explicit insecure localhost/demo mode). Operators must set the token before any shared-network Hosted.
4. **Public routes:** `GET /api/health` and `GET /api/meta` only. Meta may advertise `auth_required` / `auth_env` — never the secret.
5. **Not in scope:** OAuth, users, sessions, refresh tokens, RBAC, multi-tenant isolation.
6. **Orthogonal to M-PR1:** Valid auth does not enable `MUTINY_ALLOW_PROJECT_EXEC` or customer adapter `exec_module`. Execution isolation is **ADR-019** (accepted observe-only); implementation is **M-PR8** (not yet).

**Alternatives:** Always-on auth with startup failure if unset; per-user accounts; mTLS; API-gateway-only auth.

**Tradeoffs:** Unset token keeps local demo frictionless but is unsafe if Hosted is exposed. Single shared token is enough for single-operator Hosted, not multi-tenant cloud.

**Reconsider when:** Multi-tenant Hosted or org SSO becomes a product requirement (superseding ADR).

---

## ADR-019 — Hosted observe/lineage only; customer Python executes on CLI

**Problem:** Hosted `CampaignSupervisor` can load customer `.mutiny/adapter.py` via `load_adapter_factory` → `importlib` `exec_module` in the shared API process (`project_path` → `_make_adapter`). That is acceptable for Local CLI (same trust as `pytest`) but violates SYSTEM_DESIGN §20 for a control plane: authenticated or not, a reachable Hosted that executes arbitrary customer trees is an RCE / host-FS write class risk. M-PR1 (`MUTINY_ALLOW_PROJECT_EXEC`) is a kill-switch, not isolation. Target B (Production Hosted) needs a durable execution model.

**Decision (Option A — observe-only Hosted):**

1. **Target architecture:** Hosted API/UI is a **control, persistence, and lineage plane** — campaigns, SSE, SQLite artifacts, minimize/regression *metadata*. It does **not** execute customer project Python in the shared API process.
2. **Customer adapter execution** belongs on the **developer machine** (primary: `mutiny run` / `mutiny test` → Core → Adapter #1), same trust domain as Local CLI (ADR-017). Hosted may later accept **uploaded events/artifacts** (or equivalent push) from that local runner; that ingestion path is **M-PR8**, not this ADR’s implementation.
3. **Trusted in-process harness** (`target=in_process_demo`) may remain in the API for reliability demos — it is Mutiny-shipped code, not customer `project_path`.
4. **Interim (current code, until M-PR8):** M-PR1 stays fail-closed by default; `MUTINY_ALLOW_PROJECT_EXEC=1` remains single-operator localhost risk acceptance only — **not** the Target B model and **not** a sandbox.
5. **Orthogonal:** ADR-020 (policy-derived seeds) and ADR-021 (Bearer token) are unchanged. Auth does not grant execution; observe-only does not replace auth.
6. **Does not supersede** ADR-020 or ADR-021. **Complements** ADR-017/018. **Partially supersedes** ADR-001’s implication that Hosted is the primary *execution* surface (product priority already moved by ADR-017; this ADR locks Hosted *execution* out of customer Python). **Does not** adopt ADR-007 workers for Target B; workers remain deferred (Option B rejected for now).

**Alternatives:**

| Option | Idea | Why not chosen |
|---|---|---|
| **A (chosen)** | Observe/lineage Hosted; CLI executes customer adapters | — |
| **B** | Ephemeral per-campaign worker/container with FS allowlist | Keeps remote “Run” UX but conflicts with ADR-007 MVP posture, high ops cost, still needs auth + threat model; revisit if design partners require cloud-side agent exec |
| **C** | Hosted = `in_process_demo` forever; customer projects CLI-only forever | Honest interim (overlaps M-PR1 default) but permanently shrinks Hosted product; does not define Target B lineage ingest |

**Tradeoffs:** Clear trust boundary and reuse of Local CLI security model; Hosted “Run against my project” UX must become “run locally, observe in Hosted” (UI/API redesign in M-PR8). Weaker “push button cloud fuzz” story until/unless Option B is reconsidered.

**Reconsider when:** A concrete multi-tenant or CI-remote requirement forces server-side customer execution with a written worker threat model (new ADR superseding this one toward Option B); or observe-only ingest proves insufficient for the primary Hosted UX.

**M-PR8A/B/C/D follow-up:** The CLI → Hosted ingestion envelope, Hosted `/api/ingest/v1/*` observe-only API, CLI `--hosted` = local exec + end-of-run sync, and Web observe-only copy are specified/implemented per [HOSTED_INGESTION.md](./HOSTED_INGESTION.md). **Remove production customer exec (M-PR8E)** remains. This does **not** supersede ADR-020/021.
