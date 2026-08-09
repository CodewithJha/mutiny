# Mutiny — Architecture

| Field | Value |
|---|---|
| **Status** | Canonical for package boundaries and constraints |
| **Last updated** | 2026-08-07 |
| **Related** | [PRD](./PRD.md) · [SYSTEM_DESIGN](./SYSTEM_DESIGN.md) · [DECISION_LOG](./DECISION_LOG.md) |

This document defines **how Mutiny is structured** and **what is allowed to depend on what**. It does not narrate product vision (see PRD) or runtime sequences (see SYSTEM_DESIGN).

---

## 1. Architecture philosophy

Mutiny is a **behavioral fuzz-testing engine**: a **small trusted kernel** wrapped by thin interfaces.

- The **kernel** (`packages/mutiny_core`) decides what a policy violation is, how campaigns search, and how exploits become regressions. It is **framework-independent**.
- The **adapter layer** is the only place framework-specific glue lives. Additional adapters (LangGraph, CrewAI, …) do not change Core.
- The **CLI** (`mutiny init` / `mutiny run`) is the primary developer surface for installing Mutiny into a customer agent project.
- The **Hosted platform** (`apps/api`, `apps/web`) makes campaigns operable and visible (lineage, SSE, persistence).
- **Adapters** bridge Core to targets. Hackathon MVP Adapter #1: **OpenAI Agents SDK** → developer’s local agent. Bundled demo agent = example adapter target / harness.
- **Integrations** (Skills, MCP, CI, future framework adapters) invoke the same kernel or Hosted API. They do not fork logic.

We optimize for:

1. Correctness of the acceptance oracle  
2. Debuggability via traces  
3. A clean path from customer project → adapter layer → Core campaign  
4. Future OSS extensibility without rewriting the kernel  

We explicitly do **not** optimize for microservice sprawl, multi-cloud topology, or shipping every framework adapter in MVP (**one production-quality adapter: OpenAI Agents SDK**).

---

## 2. Design principles

These principles are binding. New features must not violate them without an ADR in [DECISION_LOG.md](./DECISION_LOG.md).

| Principle | Meaning |
|---|---|
| **Proof over probability** | A shipping claim of “violation found” requires deterministic evaluation on a persisted trace—not an LLM opinion. |
| **AI proposes; code proves** | Models generate/mutate attack text. Code decides policy outcomes and regression PASS/FAIL. |
| **Deterministic acceptance** | `violated ∈ {0,1}` for implemented rules is pure and testable. |
| **One Core** | Campaign, policy, fitness, mutate, minimize, regress live in one package. No second engine. |
| **Adapter-first** | Core → Adapter Layer → framework adapter → customer project. Framework quirks never leak into Core (ADR-018). |
| **Customer project first** | Primary path is Mutiny Core → adapter → user project. Hosted and sample/demo are secondary. |
| **Regression by default** | A verified exploit should be saveable as a permanent test. Discovery without regression is incomplete. |
| **Every exploit becomes a permanent test** | Minimized reproductions are first-class artifacts, not chat logs. |
| **Human-readable evidence** | Tool-call JSON, rule IDs, and lineage must be inspectable (CLI and/or Hosted UI). |
| **Small trusted kernel** | Core stays free of FastAPI, React, and DB drivers. |
| **Safety by construction** | MVP targets are local projects / in-process / localhost; authorized-use expectations required. |

---

## 3. Layering

```
┌──────────────────────────────────────────────────────────┐
│  Presentation     apps/web  (Hosted; secondary)          │
├──────────────────────────────────────────────────────────┤
│  Application      apps/api  (HTTP, SSE, DB; secondary)   │
│                   CLI: mutiny init / mutiny run (primary)│
├──────────────────────────────────────────────────────────┤
│  Domain / Core    packages/mutiny_core                   │
│                   (framework-independent engine)         │
├──────────────────────────────────────────────────────────┤
│  Adapter Layer    TargetAdapter port + implementations   │
│                   • OpenAI Agents SDK Adapter (MVP #1)   │
│                   • Future: LangGraph, CrewAI, …         │
│                   • Example: demo_agent adapter          │
├──────────────────────────────────────────────────────────┤
│  Targets          Customer agent project                 │
│                   Sample / apps/demo_agent (reference)   │
├──────────────────────────────────────────────────────────┤
│  Integrations     Skills / MCP / CI                      │
└──────────────────────────────────────────────────────────┘
```

**Dependency direction:** outer layers may call inward. Core must not import apps, integrations, or framework SDKs.

```
CLI / web → (api optional) → mutiny_core → Adapter Layer → OpenAI Agents SDK Adapter → Customer project
                                              ↘ example: demo_agent (interim harness)
                                              ↘ future adapters (same port; Core unchanged)
integrations/* → api (preferred) or mutiny_core (offline replay)
```

Canonical product hierarchy (never reverse):

```
Mutiny (behavioral fuzz-testing engine)
  → Adapter Layer
    → OpenAI Agents SDK Adapter   (Hackathon MVP first adapter)
    → Future adapters             (LangGraph, PydanticAI, CrewAI, AutoGen, HTTP, …)
      → Customer Project
```

---

## 4. Package boundaries

### `packages/mutiny_core` — domain kernel

**Owns**

- Policy schema + evaluator  
- Attack genome models  
- Campaign orchestration (in-memory / caller-driven)  
- Mutation operators (including LLM client *ports*, not provider SDKs hard-wired as business logic)  
- Fitness scoring  
- Minimization  
- Regression artifact format + replay pure functions  
- Target **adapter interface** (`TargetAdapter`)  
- Trace / event **payload types** (not persistence)

**Must not contain**

- FastAPI / Starlette routes  
- React / Next.js  
- SQLAlchemy/SQLite session management as a required dependency of domain functions  
- UI formatting  
- MCP protocol servers  
- Framework-specific SDK glue (OpenAI Agents SDK, LangGraph, …) — that belongs in adapter implementations outside Core business rules

**Allowed**

- Pydantic models  
- Pure Python  
- Optional protocol/ABC for `LLMClient`, `TargetAdapter`, `Clock`, `IdFactory`  

Persistence is **not** Core’s job. The API or CLI persists what Core returns.

### CLI / init surfaces (intended package ownership — docs; implement per IMPLEMENTATION_PLAN)

**Owns (planned)**

- `mutiny init` — generate `.mutiny/adapter.py`, `policy.yaml`, `mutiny.yaml` in the customer project  
- `mutiny run` — load adapter + policy + config; drive Core campaign; write regressions  
- `mutiny test` — regression replay (P1)  

**Must not contain**

- Reimplemented policy evaluation, fitness, or mutation logic  

Placement may be `integrations/cli` or a published `mutiny` package entrypoint; Core remains the engine.

### OpenAI Agents SDK adapter (MVP — planned)

**Owns**

- Loading the developer’s agent via OpenAI Agents SDK  
- Mapping SDK tool calls / turns → `AdapterTurnResult` / traces  
- Session reset/step for campaigns  

**Must not contain**

- Policy evaluation or campaign search logic  

### `apps/api` — Hosted application layer

**Owns**

- REST + SSE endpoints  
- SQLite schema and repositories  
- Mapping DB rows ↔ Core objects  
- Campaign task supervision (`asyncio`)  
- Authz attestation checks, rate limits, target allowlisting  
- Wiring concrete adapters and LLM clients (including interim demo adapter)

**Must not contain**

- Reimplemented policy evaluation  
- Custom fitness math divergent from Core  
- Mutation prompt logic copied out of Core  

### `apps/web` — Hosted presentation

**Owns**

- Campaign UX, evolution graph, exploit workflow, tests page  
- SSE consumption and REST calls  

**Must not contain**

- Policy evaluation  
- Direct model calls for judging violations  

### `apps/demo_agent` — reference / sample target (not primary product)

**Owns**

- Deliberately vulnerable support agent used as **example project**, docs target, and reliability harness  
- Mock tools and soft system prompt  
- Optional HTTP chat surface used by Hosted interim path  

**Must not contain**

- Mutiny campaign logic  
- Policy evaluator (policies are Mutiny’s, not enforced inside the vulnerable demo path)

### Future / secondary integrations

| Path | Role |
|---|---|
| LangGraph / CrewAI / PydanticAI / HTTP adapters | Roadmap (Beta/v1) — see [ROADMAP](./ROADMAP.md) |
| `integrations/mcp` | MCP tool wrappers around API/Core (post-MVP) |
| `integrations/skills` | Instructional Skill markdown |

**Must not contain** mutation, policy, or fitness logic.

### `examples/`

Checked-in policies, sample regressions, sample OpenAI Agents SDK project configs, demo fixtures. Not the primary shipped product.

### `tests/`

Unit tests prefer Core. Integration tests may boot API + sample/demo adapter. Reliability tests enforce smoke flake budgets.

---

## 5. Module responsibilities (Core)

| Module | Responsibility | Side effects |
|---|---|---|
| `policy` | Parse/validate rules; evaluate traces | None |
| `genome` | Attack candidate structure | None |
| `adapter` | `TargetAdapter` ABC | I/O only in implementations |
| `trace` | Trace / PolicyHit models | None |
| `fitness` | Score traces given PolicySet | None |
| `mutate` | Produce child genomes | May call `LLMClient` port |
| `campaign` | Generational loop driving adapter + fitness + mutate | Calls ports; emits events via callback |
| `minimize` | Delta-debug genomes | Re-exec via adapter |
| `regress` | Serialize/replay regression artifacts | Replay via adapter |
| `events` | Typed event payloads for SSE / CLI bridging | None |

---

## 6. Dependency rules (enforce in review)

1. `mutiny_core` must not import `apps.*` or `integrations.*`.  
2. `apps.web` must not import `mutiny_core` directly in MVP (talk to API only)—keeps browser boundary clean.  
3. `apps.api` is the only layer that speaks SQL for Hosted.  
4. Integrations / CLI must not import `apps.web`.  
5. No circular imports between campaign ↔ mutate ↔ fitness; use unidirectional calls from campaign.  
6. Provider SDKs (OpenAI/Featherless) and agent-framework SDKs live behind ports / adapter implementations—**business rules stay provider- and framework-agnostic**.  
7. New frameworks → new adapter implementations; do not broaden Core for framework quirks. Campaign, policy, minimize, regression, and fitness stay framework-independent.

---

## 7. Ownership (who changes what)

| Area | Primary owner mindset |
|---|---|
| Policy semantics | Core + ADR if changing acceptance meaning |
| OpenAI Agents SDK adapter (Adapter #1) | Adapter module + tests |
| Future framework adapters | New adapter modules; Core unchanged |
| CLI init/run | CLI package / entrypoint |
| Hosted UX | `apps/web` |
| Persistence / SSE | `apps/api` |
| Sample/demo reliability | `apps/demo_agent` + campaign config (harness only) |
| Future adapters / MCP | `integrations/*` after MVP adapter is green |

Cross-cutting changes to acceptance oracles require ADR + Core tests before UI work.

---

## 8. Architectural constraints (hard limits)

These exist to prevent demo failure and architecture drift. Override only via ADR.

### Campaign search budget

| Constraint | MVP default | Hard max |
|---|---|---|
| Concurrent campaigns per process | 1 | 1 |
| Population size `N` | 8 | 12 |
| Generations `Gmax` | 6 | 8 |
| Max user turns per genome | 4 | 6 |
| Max mutation LLM retries | 2 | 3 |
| Candidate execution parallelism | 2 | 3 |

### Latency & duration

| Constraint | Target / limit |
|---|---|
| Max wall-clock campaign duration | 12 minutes (soft stop); hard cancel at 15 |
| Target turn timeout | 30 s |
| Candidate timeout | 120 s |
| Minimize wall-clock budget | 3 minutes |
| Regression replay timeout per test | 120 s |
| SSE client idle tolerance | Reconnect via REST snapshot |

### Payload & memory

| Constraint | Limit |
|---|---|
| Max message chars per turn | 4_000 |
| Max trace JSON size per candidate | 512 KB |
| Max events retained per campaign | 10_000 |
| Assumed memory (single machine) | ≤ 2 GB process RSS for MVP demos |

### Model / token budget

| Constraint | Limit |
|---|---|
| Max target tokens per turn (completion) | provider-dependent; cap `max_tokens` ≤ 1024 for target replies |
| Max mutation completion tokens | 1_024 |
| Max campaigns without health check | Refuse start if Hosted `/api/health` model probe fails |

### Safety

| Constraint | Rule |
|---|---|
| Allowed targets (MVP) | Local customer project via adapter; in-process sample/demo; `http://127.0.0.1` / `localhost` only |
| Open internet targets | Forbidden in MVP |
| Real side-effecting tools | Forbidden in demos (mocks); customer projects must attest authorized testing |
| Authorization attestation | Required to start Hosted campaign; CLI documents authorized use |

### Framework scope (MVP)

| Constraint | Rule |
|---|---|
| Supported MVP adapter | Adapter #1: OpenAI Agents SDK (Core supports more via same interface) |
| LangGraph, CrewAI, PydanticAI, AutoGen, MCP targets | Out of MVP — ROADMAP |

---

## 9. Why this architecture exists

| Pressure | Response |
|---|---|
| Flaky LLM judging destroys trust | Deterministic Core oracle |
| Demo-as-product confuses buyers | Customer project + adapter is primary; demo is sample |
| Dual engines waste time | One Core; CLI + Hosted clients |
| UI logic drifting into “soft” security claims | Web cannot evaluate policies |
| Persistence coupling blocking tests | Core pure; API owns SQLite |
| Framework sprawl | Hard MVP lock to OpenAI Agents SDK |
| Future CLI/MCP forks | Clients call Core/API; no logic copy |

---

## 10. Subsystems (summary)

Detailed behavior lives in [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md).

| Subsystem | One-line purpose |
|---|---|
| Policy Engine | Decide if a trace violates explicit rules |
| Campaign Engine | Search adversarially across generations |
| Mutation Engine | Produce policy-focused child attacks |
| Fitness Engine | Guide search; gate on deterministic violation |
| Trace Engine | Record evidence |
| Minimizer | Shrink reproducing exploits |
| Regression Engine | Permanent PASS/FAIL artifacts |
| OpenAI Agents SDK Adapter | Bridge Core to the developer’s agent |
| CLI init/run | Scaffold and drive campaigns in-project |
| Hosted API | Operate and persist campaigns (secondary) |
| Hosted Web | Make search and proof legible (secondary) |
| Sample / Demo Agent | Reference vulnerable target for docs + harness |
| Future integrations | Additional adapters and clients |

---

## 11. Explicit non-architecture (do not add)

Without a new ADR and a concrete MVP need:

- Vector databases / RAG “attack memory”  
- Kafka / Celery / Redis-required queues  
- Kubernetes  
- Multi-tenant control planes  
- Second policy engine in the agent under test for the vulnerable sample path  
- LLM-as-judge acceptance path  
- Multiple framework adapters in MVP  

---

## 12. Evolution rules

1. New target types → new adapter implementation; Core interface stable.  
2. New policy primitives → Core evaluator + unit tests + ADR.  
3. New Hosted pages → API contracts first.  
4. New integrations → call existing API/Core; no logic copy.  
5. Softening sample/demo agent for reliability → document in demo config; never fake violations in DB.  
6. Customer-project path remains primary even when Hosted still wires the interim demo adapter in code.
