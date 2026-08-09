# Mutiny — Product Requirements Document

| Field | Value |
|---|---|
| **Document** | PRD — product source of truth |
| **Product** | Mutiny |
| **Status** | Active |
| **Last updated** | 2026-08-07 |
| **Build window** | Current open-source scope |
| **Primary surface** | Local install into the developer’s AI agent project (CLI: `mutiny init` / `mutiny run`); Adapter #1 = OpenAI Agents SDK |
| **Secondary surfaces** | Hosted API + UI (lineage / ops); bundled sample project as reference |

### Related engineering docs

| Need | Document |
|---|---|
| Package boundaries, constraints | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Runtime behavior, lifecycles | [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) |
| Milestones / DoD | [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) |
| Competitive detail | [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md) |
| ADRs | [DECISION_LOG.md](./DECISION_LOG.md) |
| Phased future work | [ROADMAP.md](./ROADMAP.md) |
| Live demo | [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) |

**Conflict rule:** Product intent → this PRD. Hard boundaries → ARCHITECTURE. Runtime contracts → SYSTEM_DESIGN. Sequencing → IMPLEMENTATION_PLAN. Reconcile docs; do not silently diverge in code.

---

## 1. Vision

Agents are becoming the control plane for software actions: refunds, emails, account changes, deployments, data access. Today we evaluate their *words*. Tomorrow we must evaluate their *actions*.

**Mutiny’s vision** is a general **behavioral fuzz-testing engine** for AI agents—making behavioral security as routine as unit tests and fuzzing are for ordinary software—continuous, deterministic where it matters, and permanently regressable—**inside the developer’s own agent project**, reached through a thin adapter layer.

---

## 2. Mission

1. Capture what an agent must **never** do as explicit, machine-checkable policies over tool use.  
2. **Search** adversarially for conversations that cause those policies to break **in the developer’s agent**.  
3. **Prove** breaks with execution traces—not vibes.  
4. **Minimize** exploits to understandable reproductions.  
5. **Freeze** discoveries as regression tests that fail until the agent is fixed—and pass afterward.

---

## 3. Product Thesis

> **Mutiny is a behavioral fuzz-testing engine for AI agents.** Developers install it into their own project, connect via an adapter, and fuzz explicit tool-use invariants until verified failures become permanent regressions.

**What's included today:** support for OpenAI Agents SDK projects through Adapter #1. Future frameworks plug in as additional adapters on the same Core.

```
INSTALL into your agent project (Adapter #1: OpenAI Agents SDK)
  → INIT adapter + policy + config
  → DEFINE invariants
  → RUN campaign (discover tools → evolve attacks)
  → OBSERVE tool-call traces
  → VERIFY violations deterministically
  → MINIMIZE
  → SAVE as regression tests
```

**AI proposes. Code proves.**

**Current scope:** **one production-quality adapter** — OpenAI Agents SDK. Other frameworks are roadmap adapters (same engine).

---

## 4. Problem Statement

### The shift

LLM apps are increasingly **agents**: systems that call tools, mutate state, and take irreversible actions—usually built with a framework. Primary user: a developer building an AI agent. Current-scope assumption: their project uses the OpenAI Agents SDK (first adapter).

### What breaks

System-prompt “policies” are non-executable, easy to socially engineer, invisible in CI, and not tests. Real failures look like:

- `issue_refund({ amount: 850, approved: false })`  
- `delete_account({ confirmed: false })`  
- `send_email({ recipient: "attacker@evil.com" })`  

These are **defects in action policy**, not merely bad chat text.

### What today’s workflows miss

1. Prompt review ≠ runtime proof under attack  
2. Manual red teaming doesn’t leave regressions  
3. Jailbreak scanners optimize for prohibited *text*, not *business tool invariants*  
4. Eval harnesses measure cases; few products make **install → search → prove → minimize → regress** the default builder experience **against your own agent**  

### Cost of inaction

Fraud, data loss, compliance incidents, and eroded trust—while agent deployment accelerates.

---

## 5. Why Existing Solutions Are Not Enough

Existing tools are valuable; they are not this product.

| Gap | Why it hurts |
|---|---|
| Jailbreak catalogs | Weak mapping to *your* refund/delete/email rules |
| LLM-as-judge success | Flaky CI ground truth for tool args |
| Specialist frameworks | High setup cost; weak product loop for app teams |
| Eval-only workflows | Strong measurement; weaker *search* toward a named invariant |
| Static “LLM repo audit” | Suggestion without dynamic adversarial proof |
| Hosted-only demo agents | Doesn’t test the agent you ship |

**Full analysis:** [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md).

**Approved positioning:** Mutiny is *AFL for agent tool policies*—a behavioral fuzz-testing **engine** you install into **your agent**—not an OpenAI Agents SDK testing tool, not a hosted vulnerable-demo product, not the first agent red-teaming system. The OpenAI Agents SDK adapter is Adapter #1 (first integration), not the product definition.

---

## 6. Competitive Landscape (summary)

Closest neighbors: **Promptfoo** (policies, trajectories, CI), **Garak Agent Breaker** (tool-aware adaptive attacks), **PyRIT** (orchestration library), **PromptFuzz-like** tools (evolutionary text attacks).

Mutiny’s wedge is the **composed engine loop installed into your project**: adapter layer + deterministic tool-arg oracle + policy-guided evolutionary search + minimize → regression (+ optional Hosted genealogy). Which framework adapter is present is an implementation detail.

Do not claim invention of multi-turn attacks, custom policies, evolutionary prompts, or CI evals in the abstract.

---

## 7. Target Users

### Primary

| Persona | Need |
|---|---|
| Developer building an AI agent | Fuzz *their* agent’s tool policies without rewriting the stack (current scope: OpenAI Agents SDK projects) |
| AI engineer on a product team | Turn verified failures into lasting regressions in-repo |
| OSS contributor | Extend the engine loop via adapters |

### Secondary (later)

Security engineers (CI), platform teams (policy packs), specialist red teamers (faster reproduction).

### Non-users (now)

Third-party attack seekers; toxicity-only buyers; day-one enterprise SSO tenants; teams needing LangGraph/CrewAI/etc. on day one (roadmap adapters).

---

## 8. Primary Use Cases

1. Own an AI agent project (current scope: OpenAI Agents SDK, e.g. `customer-agent/`).  
2. Install Mutiny (`pip install mutiny-ai`, or git/source until published) → `mutiny init` (adapter, `policy.yaml`, `mutiny.yaml`).  
3. Connect the agent in `.mutiny/adapter.py`.  
4. `mutiny run` — discover tools, run evolutionary campaign, find deterministic violations.  
5. Inspect tool-call evidence; minimize; save regression.  
6. Replay until the agent fix lands (FAIL → PASS).  
7. Optionally open Hosted UI for live lineage / campaign ops.

---

## 9. Secondary Use Cases

1. Run against the **bundled sample / demo project** as a docs example or reliability harness.  
2. CLI regression replay in CI.  
3. Skills / MCP invoking the same API/Core (roadmap).  
4. Human-approved policy suggestions from a known layout.  
5. Additional framework adapters (LangGraph, CrewAI, …) — roadmap.  
6. Human-readable finding export.

---

## 10. Non Goals

- Generic jailbreak mega-library  
- LLM judges as acceptance for tool-arg policies  
- Open-internet attack-as-a-service  
- Static-only “vulnerabilities” without dynamic proof  
- Every agent framework on day one (**current scope = one production-quality adapter: OpenAI Agents SDK**)  
- Kubernetes-scale fuzz infra in current scope  
- Replacing Promptfoo/Garak wholesale  
- Treating the bundled demo agent as the primary product  
- Defining Mutiny as an OpenAI Agents SDK testing tool  
- Two independent products that fork Core logic  

---

## 11. Core Product Principles

Binding product principles (engineering elaboration in ARCHITECTURE):

1. **Your agent first** — primary workflow is Mutiny against the developer’s local agent project  
2. **One engine** — Core owns search/oracle/regress; adapters are the only framework-specific layer; CLI and Hosted are clients  
3. **Invariants over vibes**  
4. **AI proposes; code proves**  
5. **Traces are evidence**  
6. **Minimize before you moralize**  
7. **Regression by default** — every exploit should become a permanent test  
8. **Safety by default**  
9. **Honesty compounds**  
10. **Demo reliability is a feature** (sample project / harness OK; never fake violations)  
11. **Simplicity wins** — one production-quality adapter in current scope; architecture supports more without Core changes  

---

## 12. Success Metrics

### Current scope

| Metric | Target |
|---|---|
| Real policy violation via search against an adapter-connected target (OpenAI Agents SDK sample or user project) | Yes |
| Install path comprehensible | `pip install` → `mutiny init` → `mutiny run` |
| Smoke reliability (harness) | ≥ 2 / 3 runs |
| Time to first violation (warm) | ≤ 10 minutes |
| Saved exploits re-verify | 100% |
| FAIL → PASS after documented fix | Live |
| Thesis comprehensible | ≤ 30s (CLI story + optional Hosted) |

### Directional (next)

Time-to-first-policy ↓ · findings→regressions % ↑ · false positives on predicates ~0 · repeat breaks after fix ↓ · additional framework adapters without Core forks

---

## 13. System Overview (product view)

```
Customer agent project
        ↑
OpenAI Agents SDK Adapter   ← Adapter #1 (shipped)
        ↑
   Adapter Layer            ← future adapters without Core changes
        ↑
   Mutiny Core              ← behavioral fuzz-testing engine
        ↑
   CLI (primary)  ·  Hosted API/UI (secondary ops)
```

Bundled demo / sample project = example adapter target, not the center of the product story.

Runtime behavior, trust boundaries, and lifecycles: [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md).  
Package ownership and hard limits: [ARCHITECTURE.md](./ARCHITECTURE.md).

**Note:** Persistence for Hosted is owned by the Hosted API. Core does not own the database. Local `mutiny run` may persist regressions/artifacts under the customer project (see SYSTEM_DESIGN).

---

## 14. High-Level Architecture (pointer)

Canonical diagrams and dependency rules live in ARCHITECTURE and SYSTEM_DESIGN.

Current runtime defaults: single machine · Adapter #1 (OpenAI Agents SDK) · CLI init/run · FastAPI + Next.js Hosted (optional) · SQLite (Hosted) · Featherless models · sample/demo project as reference harness.

---

## 15. Product Components

| Component | Product responsibility |
|---|---|
| Policy Engine | Machine-checkable tool-use invariants |
| Campaign + Mutation + Fitness | Search toward those invariants |
| Trace Engine | Evidence |
| Minimizer + Regression | Permanent tests |
| Adapter Layer | Framework-neutral port; framework glue lives only in adapter impls |
| OpenAI Agents SDK Adapter | Adapter #1 — bridge Core ↔ developer’s agent |
| CLI (`mutiny init` / `mutiny run`) | Primary developer entrypoint |
| Hosted API + Web | Lineage, ops, optional campaign UX |
| Sample / demo agent | Reference implementation + testing harness |
| Future integrations | Additional adapters (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP, …), Skills, MCP, CI |

---

## 16. Hosted Mutiny Roadmap

**Canonical phased roadmap:** [ROADMAP.md](./ROADMAP.md).

- **Current scope:** behavioral fuzz engine + Adapter #1 (OpenAI Agents SDK) + CLI (+ sample project); Hosted as secondary visualization/ops  
- **Beta:** LangGraph / CrewAI / PydanticAI / AutoGen / HTTP adapters on the same interface; MCP/Skills; history/reports  
- **v1:** single-tenant Hosted, CI Action, stable APIs  
- **Long-term:** teams, connectors, policy pack ecosystem  

---

## 17. Developer Integrations Roadmap

Detail in ROADMAP.

| Stage | Integration |
|---|---|
| P0 | CLI `mutiny init` / `mutiny run` + Adapter #1 (OpenAI Agents SDK) |
| P1 | CLI regression replay (`mutiny test`) |
| Stretch | One Skill |
| Beta | Additional framework adapters; MCP + multi-environment skills |
| v1 | GitHub Action |

Integrations must not reimplement Core logic.

---

## 18. Feature Prioritization

### P0

Core loop · deterministic evaluator · Adapter #1 (OpenAI Agents SDK) · `mutiny init` / `mutiny run` · verified violation · minimize+re-exec · regression replay · safety binds · sample project as reference

### P1

Hosted API/UI lineage against sample or attached run · evolution graph · observability · reliability suite · startup UX · backup recording

### P2

MCP · localhost HTTP adapter · LangGraph / CrewAI / PydanticAI adapters · second exploit narrative · repo policy suggestions

### P3

Multi-tenant cloud · Actions marketplace · broad static analysis · distributed workers

Milestone DoD: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

---

## 19. Technical Requirements

| Area | Requirement |
|---|---|
| Core/CLI | Python 3.11+, Pydantic v2; Typer (or equivalent) for CLI |
| Adapter scope | Adapter #1 = OpenAI Agents SDK; Core remains framework-neutral |
| Hosted API | FastAPI |
| Web | Next.js, TypeScript, Tailwind, shadcn/ui, React Flow |
| DB | SQLite (API-owned, Hosted) |
| Models | Featherless; Ollama/templates fallback |
| Packaging | Monorepo; user install `pip install mutiny-ai` (CLI `mutiny`); PyPI upload pending — see docs/PUBLISHING.md; optional docker-compose |

Forbidden without ADR: required Redis/Celery/Kafka, Kubernetes, vector DB, RAG stacks.

---

## 20. Functional Requirements

1. Scaffold project files via `mutiny init`  
2. Load developer agent through the adapter layer (OpenAI Agents SDK adapter)  
3. View/edit policies (`policy.yaml`)  
4. Start campaign after attestation (where Hosted) / local authorized-use expectations (CLI)  
5. Generate and evolve attack population  
6. Record traces including tool calls  
7. Deterministic violation detection  
8. Stream progress (CLI output and/or Hosted SSE)  
9. Inspect evidence and lineage  
10. Minimize with re-exec  
11. Save and replay regressions (PASS/FAIL)  
12. Refuse unsafe target classes (current scope)  

---

## 21. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Reliability | ≥2/3 smoke on pinned harness config |
| Latency | Default campaign typically 4–10 min; hard caps in ARCHITECTURE |
| Observability | Traces, metrics, health |
| Security | No open proxy; secret redaction |
| Usability | Clear install → init → run path; ≤2-minute demo narrative |
| Maintainability | Core independent of UI |
| Honesty | No unearned novelty claims; docs match adapter reality |

---

## 22–28. Engine Requirements (product-level)

Detailed algorithms and lifecycles are normative in SYSTEM_DESIGN. Product requirements that must not be lost:

| Engine | Must |
|---|---|
| **AI** | Propose/mutate only; never accept violations |
| **Mutation** | Policy-conditioned; template fallback |
| **Policy** | Pure deterministic predicates over tools/context |
| **Fitness** | Heuristic for search; `1.0` only on violation |
| **Campaign** | Bounded generations; evented; stop conditions defined |
| **Trace** | Persist evidence; fail loudly if tools unobservable |
| **Regression** | Same oracle as live; FAIL until fixed |
| **Adapter** | Stable framework-neutral `TargetAdapter` port; OpenAI Agents SDK impl = Adapter #1 |

---

## 29. Security Model (product)

- Current targets: local customer project via adapter; sample/demo in-process or localhost  
- Explicit authorization attestation (Hosted) / authorized-use messaging (CLI)  
- SSRF denials for non-allowlisted destinations  
- Redact secrets in traces  
- Single concurrent campaign  

---

## 30. Safety Model (product)

Defensive testing only. Prefer mock/sandboxed tools for demos. No credential stuffing, malware, persistence, or mass scanning features. Authorized-use expectations in UI, CLI, and README.

---

## 31. Repository Structure

Normative layout: [ARCHITECTURE.md](./ARCHITECTURE.md) §4.

---

## 32. Deployment Strategy

Today: local CLI against sample or user project; optional local Hosted. Beta+: published package + single-tenant Hosted. Complexity only when it improves reliability or onboarding.

---

## 33. Implementation Roadmap

Milestone-driven plan: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).  
Phased product roadmap: [ROADMAP.md](./ROADMAP.md).

---

## 34. Risk Register (product)

| Risk | Mitigation |
|---|---|
| No live violation | Reliability milestone; guided mode; sample project softness |
| Docs claim adapter that code lacks | Honest IMPLEMENTATION_PLAN DoD; sample/demo harness labeled as reference |
| Model outage | Fallbacks; backup recording |
| “Just Promptfoo/Garak” | Honest COMPETITOR_ANALYSIS; show oracle+lineage+install path |
| Scope creep to many frameworks | Hard current-scope lock: one production-quality adapter (OpenAI Agents SDK); more via ROADMAP |
| Fake-looking exploit | Real traces + lineage required |
| Overbuilt infra | Non-goals + ADRs |

---

## 35–36. Future & Demo

Future work: ROADMAP.  
Demo narration: DEMO_SCRIPT (sample agent project via Adapter #1 → init → run → Hosted).

---

## 37. Judge Story

Spine: prompts aren’t tests → install Mutiny into your agent → explicit invariants → Mutiny searches → real forbidden tool call → minimize → regression FAIL→PASS.

Canonical close: see DEMO_SCRIPT.

---

## 38. README Strategy

README is a public entrypoint, not a second PRD. Include: thesis, install flow (`pip install` / `mutiny init` / `mutiny run`), policy example, related work pointer, safety, link to `docs/`. Hosted screenshot optional. Do not lead with “our vulnerable demo agent” as the product.

---

## 39. Open Source Strategy

Permissive license at init · clean Core boundaries · good first issues on operators/adapters · reject offensive third-party targeting modules · thin maintainership later.

---

## 40. Longer-term Vision

Mutiny as the default local behavioral fuzz-testing engine for agent builders; Core embeddable in CI; framework adapters expanding carefully on the same interface; integrations making “security-test this agent” natural inside coding agents; shared policy language for agent action safety.

If Mutiny succeeds, “we have a system prompt for that” stops being an acceptable answer to “how do you know your agent won’t do X?”

---

## Appendix — Decision log pointer

High-signal decisions live in [DECISION_LOG.md](./DECISION_LOG.md) (Core package, no LLM judge, evolutionary search, monorepo, customer-project pivot ADR-017, adapter-first architecture ADR-018, etc.).
