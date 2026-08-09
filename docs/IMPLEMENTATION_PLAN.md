# Mutiny — Implementation Plan

| Field | Value |
|---|---|
| **Status** | Canonical engineering execution plan |
| **Last updated** | 2026-08-07 |
| **Build window** | Hackathon MVP |
| **Verdict** | Pivot in progress — docs ahead of install-path code |
| **Related** | [PRD](./PRD.md) · [ARCHITECTURE](./ARCHITECTURE.md) · [SYSTEM_DESIGN](./SYSTEM_DESIGN.md) · [ROADMAP](./ROADMAP.md) · [DEMO_SCRIPT](./DEMO_SCRIPT.md) · [ADR-017](./DECISION_LOG.md#adr-017--customer-owned-local-projects-primary-bundled-demo-secondary) · [ADR-018](./DECISION_LOG.md#adr-018--adapter-first-architecture) |

This plan is **milestone-driven**. Calendar days only allocate work; they do not redefine scope.

Behavioral contracts → SYSTEM_DESIGN. Boundaries → ARCHITECTURE. Product intent → PRD.

**Honest codebase note:** The repo currently implements Core + Hosted against a **bundled demo agent** (interim reference / harness). **Adapter #1** (OpenAI Agents SDK) and `mutiny init` / `mutiny run` product path are **planned**—DoD boxes below reflect that. Do not treat unchecked boxes as done. Architecture already supports additional adapters; they are **not** Hackathon critical path.

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

| ID | Milestone | Primary outcome | Status (2026-08-07) |
|---|---|---|---|
| M1 | Core | Models + policy evaluator + kernel ports tested | **Done** (existing) |
| M2 | Adapter #1 (OpenAI Agents SDK) | `TargetAdapter` impl loads a real OpenAI Agents SDK agent | **Planned** (interim: demo adapter) |
| M3 | Policy generation | `mutiny init` scaffolds adapter stub + `policy.yaml` + `mutiny.yaml` | **Planned** |
| M4 | Campaign | Generational search runs via Adapter #1 | **Partial** — Core campaign exists vs demo; customer-path pending |
| M5 | Regression | Minimize + save + PASS/FAIL replay on adapter target | **Partial** — Core engines done vs demo; customer-path pending |
| M6 | Hosted API | REST + SSE + SQLite (may attach sample/customer later) | **Done** for demo harness; attach to new adapter TBD |
| M7 | Hosted UI | Campaign → exploit → tests UX | **Done** for demo harness; narrative/wiring TBD |
| M8 | Demo | Sample project story: init → run → Hosted; reliability | **Rework needed** for new narrative |

Optional after M8 green: **M9 Integrations** (CLI `mutiny test`; Skill/MCP stretch). LangGraph/CrewAI/etc. are **roadmap adapters** — not MVP milestones — see ROADMAP. Architecture can support them without Core changes.

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

**Intent:** Hackathon builds **Adapter #1** so Mutiny talks to a developer’s (or sample) OpenAI Agents SDK agent with observable tool calls. Future adapters are roadmap; the architecture already supports more via the same `TargetAdapter` port.

**Build**

- OpenAI Agents SDK `TargetAdapter` implementation (Adapter #1)  
- Load agent from project path / module specified after `mutiny init`  
- Map SDK turns → `AdapterTurnResult` / traces  
- Explicit failure if tools cannot be observed  
- Keep all OpenAI-specific imports inside this adapter — none in Core  

**Interim (today):** `InProcessDemoAdapter` + `apps/demo_agent` remain as reference harness only.

**Definition of Done**

- [ ] Adapter runs a real OpenAI Agents SDK agent conversation and records tool calls in trace JSON  
- [ ] `adapter.context()` returns deterministic facts usable by policies  
- [ ] Failure if tools cannot be observed is explicit  
- [ ] No campaign/policy/fitness/minimize/regression logic inside the adapter  
- [ ] Core remains importable without the OpenAI Agents SDK
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

- [ ] `mutiny init` in an empty/sample OpenAI Agents SDK project creates the three artifacts  
- [ ] Generated `policy.yaml` validates against Core PolicySet schema  
- [ ] Stub adapter imports and documents connection points  
- [ ] No claim that generated policies are verified without a campaign  

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

- [ ] N×G campaign completes via OpenAI Agents SDK adapter without requiring Hosted UI  
- [ ] Candidates have parent/generation metadata  
- [ ] Fitness in `[0,1]` with violation ⇒ `1.0`  
- [ ] At least one run can produce `violated=true` with real tool evidence on sample or user agent (no synthetic insertion)  

*Core campaign vs demo may remain green as a harness while M2/M4 customer path is unfinished.*

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

- [ ] Minimized genome still violates under re-exec on OpenAI Agents SDK adapter  
- [ ] Save refused if not reproducible  
- [ ] Documented agent fix flips FAIL → PASS on same artifact  
- [ ] Artifacts land in the customer/sample project path by default  

---

### M6 — Hosted API

**Intent:** Optional control plane for lineage / ops.

**Build**

- FastAPI routes per SYSTEM_DESIGN Hosted section  
- SQLite repositories  
- SSE event fan-out  
- `/api/health`  
- Attestation + localhost/in-process/sample allowlist  
- Campaign asyncio supervisor (concurrency=1)  
- **Later:** attach OpenAI Agents SDK / project adapter (not required to keep existing demo wiring green)  

**Definition of Done**

- [x] Create/start campaign via HTTP (demo harness)  
- [x] SSE emits `candidate.scored` / `violation.detected`  
- [x] Minimize + regression endpoints enforce re-exec gate  
- [x] Core still has no SQL  
- [ ] Campaign can target OpenAI Agents SDK adapter / sample project (planned)  

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
- [ ] UI narrative / wiring supports sample OpenAI Agents SDK project story (planned)  

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
- [x] Smoke gate green on pinned models (interim demo harness)  
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
- Additional framework adapters — **not** part of MVP critical path  

**Definition of Done (CLI subset)**

- [ ] FAIL → fix → PASS via CLI using same artifact as campaign  

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
| No Hosted retarget | Demo Hosted against sample via interim wiring; CLI story first |
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
- MVP adapter lock: Adapter #1 = OpenAI Agents SDK only; Core stays framework-neutral  
- Future adapters (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP) are ROADMAP — architecture supports them without Core forks  
- Pin models in config after first green adapter campaign  
- Redact secrets in traces  
- Unit-test oracle and minimizer preferentially  
- Label interim demo wiring clearly in UX/docs  

---

## 6. Out of scope for this plan

See ROADMAP stages beyond Hackathon MVP (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP adapters, MCP, multi-tenant). Those are **new adapters on the same interface**. Do not schedule them into the MVP critical path.

---

## 7. Handoff criteria to “implementation complete” (post-pivot)

M1 done; M2–M5 DoD checked for OpenAI Agents SDK path; M6–M7 either retargeted or explicitly accepted as harness-backed with honest demo labeling; M8 new narrative rehearsed. M9 CLI test strongly preferred for FAIL→PASS beat.
