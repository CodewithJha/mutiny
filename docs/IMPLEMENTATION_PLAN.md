# Mutiny — Implementation Plan

| Field | Value |
|---|---|
| **Status** | Canonical engineering execution plan |
| **Last updated** | 2026-09-09 |
| **Build window** | Current open-source scope |
| **Verdict** | Adapter #1 + CLI + observe-only Hosted shipped in `0.1.0` tree; Hosted security hardening (M-PR8E, P0-3, P0-1/P0-4, P1-2) landed — Target B / 1.0 not claimed |
| **Related** | [PRD](./PRD.md) · [ARCHITECTURE](./ARCHITECTURE.md) · [SYSTEM_DESIGN](./SYSTEM_DESIGN.md) · [ROADMAP](./ROADMAP.md) · [PRODUCTION_READINESS](./PRODUCTION_READINESS.md) · [HOSTED_INGESTION](./HOSTED_INGESTION.md) · [DEMO_SCRIPT](./DEMO_SCRIPT.md) · [ADR-017](./DECISION_LOG.md#adr-017--customer-owned-local-projects-primary-bundled-demo-secondary) · [ADR-018](./DECISION_LOG.md#adr-018--adapter-first-architecture) · [ADR-019](./DECISION_LOG.md#adr-019--hosted-observelineage-only-customer-python-executes-on-cli) |

This plan is **milestone-driven**. Calendar days only allocate work; they do not redefine scope.

Behavioral contracts → SYSTEM_DESIGN. Boundaries → ARCHITECTURE. Product intent → PRD. Ship/no-ship gates → PRODUCTION_READINESS.

**Honest codebase note:** The repo implements Core + Adapter #1 (OpenAI Agents SDK) + CLI (`init` / `run` / `test`) + sample project + Hosted API/UI. Hosted customer path is **observe-only** (CLI executes; ingest sync). Trusted `in_process_demo` remains. Architecture already supports additional adapters; they are **not** on the current critical path.

---

## 0. Execution rules

1. Finish a milestone’s **Definition of Done** before starting the next, unless a parallel track is explicitly marked.  
2. If behind, cut from the bottom of [ROADMAP](./ROADMAP.md) parking lot and extra frameworks—**never** cut deterministic oracle or real tool-call proof.  
3. Do not invent behavior absent from SYSTEM_DESIGN.  
4. Any acceptance-semantics change requires an ADR.  
5. Do not pretend adapters exist in code; update this plan when they land.  
6. Keep Core framework-neutral; OpenAI-specific logic only in Adapter #1 (ADR-018).  

---

## 1. Milestone map

| ID | Milestone | Primary outcome | Status (2026-09-09) |
|---|---|---|---|
| M1 | Core | Models + policy evaluator + kernel ports tested | **Done** |
| M2 | Adapter #1 (OpenAI Agents SDK) | `TargetAdapter` impl loads a real OpenAI Agents SDK agent | **Done** (`packages/mutiny_openai_agents`) |
| M3 | Policy generation | `mutiny init` scaffolds adapter stub + `policy.yaml` + `mutiny.yaml` | **Done** |
| M4 | Campaign | Generational search runs via Adapter #1 | **Done** — local CLI / Core; Hosted customer via ingest |
| M5 | Regression | Minimize + save + PASS/FAIL replay on adapter target | **Done** — local CLI `mutiny test`; Hosted customer exec removed |
| M6 | Hosted API | REST + SSE + SQLite + observe-only ingest | **Done** for demo harness + ingest; customer Hosted exec **removed** (M-PR8E) |
| M7 | Hosted UI | Campaign → exploit → tests UX | **Done** for demo harness; observe-only copy for customer (M-PR8D) |
| M8 | Demo | Sample project story: init → run → Hosted; reliability | **Partial** — sample + reliability green; narrative polish TBD |
| M9 | Integrations (CLI test) | `mutiny test` regression replay | **Done** (CLI); Skill/MCP still roadmap |

### Hosted security / readiness (cross-cutting; see PRODUCTION_READINESS)

| ID | Outcome | Status |
|---|---|---|
| M-PR8A–E | Observe-only Hosted + ingest + CLI `--hosted` sync + Web observe + customer `exec_module` removed | **Done** |
| P0-3 | Customer `project_path` filesystem-inert / opaque on Hosted | **Done** |
| P0-1 / P0-4 | Non-loopback binds require `MUTINY_API_TOKEN`; `python -m mutiny_api` fails closed | **Done** |
| P1-2 | In-process Hosted API rate limits (not distributed) | **Done** (allowlisting remainder open) |
| P2-5 / P2-6 / P2-8 | regression `project_id`; SQLite backup/export; Dependabot/CODEOWNERS | **Not done** — do not invent completion |
| Distributed rate limits / Hosted Beta / 1.0 Target B | — | **Not done** |

---

## 2. Milestone specifications

### M1 — Core

**Intent:** Trusted evaluation exists before adapters or UI.

**Build**

- Repo skeleton per ARCHITECTURE  
- Pydantic models: PolicySet, AttackGenome, Trace types  
- `PolicyEvaluator` for `deny_tool`, `require_args`, `forbid_args`  
- Unit tests: refund/delete/deny matrices  
- Adapter **interface** (`TargetAdapter`) without framework coupling  

**Definition of Done**

- [x] `packages/mutiny_core` importable  
- [x] Evaluator tests green without network  
- [x] No FastAPI/React/SQLite inside Core  

---

### M2 — Adapter #1 (OpenAI Agents SDK)

**Intent:** Ship **Adapter #1** so Mutiny talks to a developer’s (or sample) OpenAI Agents SDK agent with observable tool calls. Future adapters are roadmap; the architecture already supports more via the same `TargetAdapter` port.

**Build**

- OpenAI Agents SDK `TargetAdapter` implementation (Adapter #1)  
- Load agent from project path / module specified after `mutiny init`  
- Map SDK turns → `AdapterTurnResult` / traces  
- Explicit failure if tools cannot be observed  
- Keep all OpenAI-specific imports inside this adapter — none in Core  

**Reference harness (today):** `InProcessDemoAdapter` + `apps/demo_agent` remain as sample/docs targets only.

**Definition of Done**

- [x] Adapter runs a real OpenAI Agents SDK agent conversation and records tool calls in trace JSON  
- [x] `adapter.context()` returns deterministic facts usable by policies  
- [x] Failure if tools cannot be observed is explicit  
- [x] No campaign/policy/fitness/minimize/regression logic inside the adapter  
- [x] Core remains importable without the OpenAI Agents SDK
---

### M3 — Policy generation

**Intent:** Developers get a usable policy + config scaffold in their project.

**Build**

- `mutiny init` CLI  
- Generate `.mutiny/adapter.py` stub (OpenAI Agents SDK)  
- Generate `policy.yaml` (template and/or tool-discovery-assisted seed; human-editable)  
- Generate `mutiny.yaml` campaign defaults  
- Document review expectation for generated policies  

**Definition of Done**

- [x] `mutiny init` in an empty/sample OpenAI Agents SDK project creates the three artifacts  
- [x] Generated `policy.yaml` validates against Core PolicySet schema  
- [x] Stub adapter imports and documents connection points  
- [x] No claim that generated policies are verified without a campaign  

---

### M4 — Campaign

**Intent:** Population search finds progress (and eventually violations) against Adapter #1.

**Build**

- Wire existing Core campaign loop to OpenAI Agents SDK adapter  
- Campaign/fitness remain framework-independent (Core unchanged for future adapters)  
- Fitness + seed genomes + template (± LLM) mutation  
- Event callback for CLI (and Hosted)  
- `mutiny run` entrypoint loading project config  

**Already true (Core vs demo harness):** campaign loop, fitness, events, template/LLM mutate.

**Definition of Done**

- [x] N×G campaign completes via OpenAI Agents SDK adapter without requiring Hosted UI  
- [x] Candidates have parent/generation metadata  
- [x] Fitness in `[0,1]` with violation ⇒ `1.0`  
- [x] At least one run can produce `violated=true` with real tool evidence on sample or user agent (no synthetic insertion)  

*Customer campaigns execute on Local CLI. Hosted receives sanitized lineage via ingest (`mutiny run --hosted`), not via Hosted `exec_module`.*

---

### M5 — Regression

**Intent:** Findings become permanent tests in the developer project.

**Build**

- ddmin minimizer + re-exec gate (Core — largely exists)  
- Regression artifact write under project (e.g. `.mutiny/tests/`)  
- Replay → PASS/FAIL via same adapter  
- CLI save/replay UX  

**Already true (Core vs demo):** minimize, artifact format, FAIL→PASS with documented demo fix.

**Definition of Done**

- [x] Minimized genome still violates under re-exec on OpenAI Agents SDK adapter  
- [x] Save refused if not reproducible  
- [x] Documented agent fix flips FAIL → PASS on same artifact  
- [x] Artifacts land in the customer/sample project path by default  

---

### M6 — Hosted API

**Intent:** Optional control plane for lineage / ops (observe-only for customer projects).

**Build**

- FastAPI routes per SYSTEM_DESIGN Hosted section  
- SQLite repositories  
- SSE event fan-out  
- `/api/health`  
- Attestation + target enum (`in_process_demo` \| `openai_agents`)  
- Campaign asyncio supervisor (concurrency=1) for **trusted `in_process_demo` only**  
- **M-PR8B:** `/api/ingest/v1/*` observe-only ingest from Local CLI  
- **M-PR8E / P0-3:** customer `project_path` adapter exec + filesystem access **removed** (`410`)  
- **M-PR7 / P0-1/P0-4:** Bearer auth; non-loopback fail-closed  
- **P1-2:** in-process rate limits  

**Definition of Done**

- [x] Create/start campaign via HTTP (**trusted demo harness**)  
- [x] SSE emits `candidate.scored` / `violation.detected`  
- [x] Minimize + regression endpoints enforce re-exec gate (demo path)  
- [x] Core still has no SQL  
- [x] Customer OpenAI Agents SDK campaigns use **CLI + ingest**, not Hosted `exec_module` (M-PR8A–E)  
- [x] Customer `project_path` is opaque / filesystem-inert on Hosted (P0-3)  

---

### M7 — Hosted UI

**Intent:** Make search and proof legible (secondary surface).

**Visual direction:** Inngest-inspired Hosted surfaces — see [DESIGN.md](./DESIGN.md) and root [PRODUCT.md](../PRODUCT.md).

**Build**

- Next.js pages: landing, campaign, exploit, policies, tests  
- SSE client + snapshot resume  
- Evolution graph (React Flow)  
- Candidate drawer with tool JSON  
- Minimize + save + run tests flows  
- Copy/UX should not present the bundled demo as the only product  

**Definition of Done**

- [x] Full loop operable from browser against current harness without CLI  
- [x] Violation evidence readable without opening DevTools  
- [x] Web does not evaluate policies locally  
- [x] Visual language matches DESIGN.md (Inngest canon)  
- [x] Observe-only product copy for customer runs (M-PR8D); Web does not POST ingest or execute customer projects  
- [ ] Further sample OpenAI Agents SDK narrative polish (optional)  

---

### M8 — Demo

**Intent:** Win the room with the **install-into-sample-project** story.

**Build**

- Sample OpenAI Agents SDK project (or wrap existing demo as that sample)  
- Rehearse [DEMO_SCRIPT](./DEMO_SCRIPT.md): clone → `mutiny init` → `mutiny run` → Hosted  
- Reliability suite on pinned harness (≥2/3)  
- README + docs aligned to customer-project primary  
- Backup recording / fixture path  
- Freeze competitive claims to [COMPETITOR_ANALYSIS](./COMPETITOR_ANALYSIS.md)  

**Definition of Done**

- [ ] Demo script path works without claiming demo-agent-as-product  
- [x] Smoke gate green on pinned models (demo reference harness)  
- [ ] 2-minute script timed ≤2:00 under new narrative  
- [x] Backup recording / fixture path exists for harness  
- [x] Safety banner + attestation present (Hosted)  
- [ ] CLI init/run demonstrated live or honestly labeled as WIP with Hosted backup  

**Artifacts**

- Pin: [`config/demo_pin.json`](../config/demo_pin.json)  
- Smoke: `scripts/smoke_reliability.py` + `tests/reliability/`  
- Cold start: [COLD_START.md](./COLD_START.md) · `scripts/dev.sh` · `docker-compose.yml`  
- Backup: `scripts/backup_fixture_demo.py` · [`examples/demo/`](../examples/demo/)  
- Claims: [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md) only  

---

### M9 — Integrations (secondary; after M8 or parallel thin track)

**Preferred**

- CLI: regression replay (`mutiny test`)  

**Stretch / roadmap**

- One Skill markdown  
- MCP wrapper  
- Additional framework adapters — **not** part of current critical path  

**Definition of Done (CLI subset)**

- [x] FAIL → fix → PASS via CLI using same artifact as campaign  

---

## 3. Suggested sequencing (post-pivot)

| Order | Focus | Notes |
|---|---|---|
| 1 | Keep M1 green | Do not regress Core oracle |
| 2 | M2 OpenAI Agents SDK adapter | Unblocks customer path |
| 3 | M3 `mutiny init` | Scaffold UX |
| 4 | M4 `mutiny run` + campaign on adapter | May reuse Core campaign |
| 5 | M5 project-local regressions | Extend existing minimizer/regress |
| 6 | Retarget M6/M7 as needed | Hosted remains valuable secondary |
| 7 | M8 narrative + reliability | DEMO_SCRIPT is source of truth |

### Slip rules

| If not done… | Cut / hold |
|---|---|
| No OpenAI Agents SDK adapter | Keep Core+demo harness for reliability; do not claim `pip install` path in live demos without labeling WIP |
| No `mutiny init` | Hand-authored sample `policy.yaml` + adapter for demo; still no fake violations |
| No Hosted retarget | Demo Hosted against sample via reference wiring; CLI story first |
| Smoke red | Backup fixture + recording; still no fake DB writes |

---

## 4. Parallelization guide

Safe parallel tracks:

| Track A | Track B |
|---|---|
| M2 OpenAI Agents SDK adapter | Docs / DEMO_SCRIPT / README (this pivot) |
| M3 CLI init | Hosted copy updates (no oracle changes) |
| Reliability harness on demo | Sample project packaging |

Unsafe parallel: two writers changing policy semantics; UI inventing event shapes not in SYSTEM_DESIGN; shipping LangGraph “while we’re here.”

---

## 5. Engineering checklist (cross-cutting)

- Respect hard limits in ARCHITECTURE §8  
- Adapter lock (current): Adapter #1 = OpenAI Agents SDK only; Core stays framework-neutral  
- Future adapters (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP) are ROADMAP — architecture supports them without Core forks  
- Pin models in config after first green adapter campaign  
- Redact secrets in traces  
- Unit-test oracle and minimizer preferentially  
- Label sample/demo wiring clearly in UX/docs  

---

## 6. Out of scope for this plan

See ROADMAP stages beyond current scope (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP adapters, MCP, multi-tenant). Those are **new adapters on the same interface**. Do not schedule them into the current critical path.

---

## 7. Handoff criteria to “implementation complete” (post-pivot)

M1–M5 **done** for OpenAI Agents SDK local path; M6–M7 **done** as observe-only Hosted + trusted demo harness (not customer Hosted exec); M8 narrative polish optional; M9 CLI `mutiny test` **done**. Hosted security hardening through P1-2 **done**. Remaining PRODUCTION_READINESS Target A/B gaps (backup, AuthZ, Dependabot, 1.0) are **out of this plan’s “done” claim** — see ROADMAP / PRODUCTION_READINESS.
