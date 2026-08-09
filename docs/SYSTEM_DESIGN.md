# Mutiny — System Design

| Field | Value |
|---|---|
| **Status** | Canonical for runtime behavior and data contracts |
| **Last updated** | 2026-08-07 |
| **Related** | [ARCHITECTURE](./ARCHITECTURE.md) · [PRD](./PRD.md) · [IMPLEMENTATION_PLAN](./IMPLEMENTATION_PLAN.md) |

This document explains **exactly how Mutiny works**. An engineer should be able to implement the system from this + ARCHITECTURE without inventing hidden behavior.

Product intent → PRD. Package rules → ARCHITECTURE. Scheduling → IMPLEMENTATION_PLAN.

---

## 1. High-level system overview

Mutiny runs **campaigns**: bounded evolutionary searches for multi-turn conversations that cause an agent to emit tool calls violating explicit policies.

**Mutiny is a behavioral fuzz-testing engine for AI agents.** Adapter #1 ships with support for OpenAI Agents SDK projects.

**Primary path:** developer’s agent project, connected via the adapter layer after `mutiny init` (OpenAI Agents SDK adapter).

```mermaid
flowchart LR
  CLI[mutiny CLI] --> C[Mutiny Core]
  H[Hosted Web] --> A[Hosted API]
  A --> C
  C --> AL[Adapter Layer]
  AL --> OAI[OpenAI Agents SDK Adapter]
  OAI --> U[Customer agent project]
  AL --> D[Sample / demo agent]
  C --> P[Policy / Fitness]
  A --> DB[(SQLite)]
  C -.events.-> CLI
  C -.events.-> A
  A -.SSE.-> H
```

**Control plane (primary):** CLI (`mutiny init` / `mutiny run`)  
**Control plane (secondary):** Hosted API  
**Decision plane:** Mutiny Core (framework-independent)  
**Evidence plane:** Traces (+ optional SQLite for Hosted)  
**Target plane:** Adapter Layer → OpenAI Agents SDK Adapter → customer agent (or sample/demo)

Adapter interfaces are **framework-neutral**. OpenAI-specific logic lives only in the OpenAI Agents SDK adapter. Campaign, policy, minimize, regression, and fitness stay framework-independent—no OpenAI leakage into Core.
---

## 2. Project bootstrap lifecycle (`mutiny init`)

```mermaid
sequenceDiagram
  participant Dev as Developer
  participant CLI as mutiny CLI
  participant FS as Project filesystem

  Dev->>CLI: mutiny init
  CLI->>FS: create .mutiny/adapter.py
  CLI->>FS: create policy.yaml
  CLI->>FS: create mutiny.yaml
  CLI-->>Dev: next steps (edit adapter, mutiny run)
```

### Generated artifacts (normative intent)

| Artifact | Role |
|---|---|
| `.mutiny/adapter.py` | Developer implements / wires `TargetAdapter` to their agent (stub: OpenAI Agents SDK) |
| `policy.yaml` | Explicit tool-use invariants (`PolicySet`) |
| `mutiny.yaml` | Campaign defaults (N, Gmax, models, stop conditions) |

`mutiny init` does **not** invent verified violations. It scaffolds connection + policy surfaces.

### Adapter contract (developer)

Adapter implementations must support a **framework-neutral** contract:

1. `reset(session_id)` — clear conversation state  
2. `step(session_id, user_message) → AdapterTurnResult` — including observable `tool_calls`  
3. `context()` — deterministic facts for policy `when` / require clauses  

If tool calls cannot be observed, campaign start **fails loudly**. Framework SDKs (OpenAI Agents SDK, etc.) are imported only inside adapter implementations—not in Core campaign/policy/minimize/regression/fitness modules.

---

## 3. Campaign lifecycle (`mutiny run` / Hosted start)

### States

```mermaid
stateDiagram-v2
  [*] --> Created
  Created --> Running: start + attestation/authorized OK
  Running --> Generation
  Generation --> Evaluating
  Evaluating --> Selecting: all candidates scored
  Selecting --> Mutating: no violation or continue
  Mutating --> Generation
  Evaluating --> Violating: fitness 1.0
  Violating --> Minimizing: optional/auto
  Minimizing --> RegressionSaved
  Selecting --> Completed: Gmax or budget
  Violating --> Completed: skip minimize
  RegressionSaved --> Completed
  Running --> Failed: adapter/model/budget
  Completed --> [*]
  Failed --> [*]
```

### Steps

1. **Load** — CLI/API loads `policy.yaml`, `mutiny.yaml`, and adapter (customer project or sample).  
2. **Create** — store campaign config (policy set, N, Gmax, target id, model pins, attestation if Hosted).  
3. **Discover** — optional tool discovery via adapter introspection / dry probe (inform policy editing; does not replace explicit policies).  
4. **Start** — health checks as applicable; concurrency=1; spawn campaign loop.  
5. **Seed** — Core builds generation-0 genomes (templates ± LLM).  
6. **Evaluate** — each candidate executed against adapter; traces scored.  
7. **Select / mutate** — elites retained; children mutated.  
8. **Stop** — first violation (configurable), Gmax, wall-clock budget, or error.  
9. **Post** — minimize + regression save (auto or user-triggered).  

### Stop conditions (priority order)

1. Hard cancel / timeout  
2. Unrecoverable adapter failure (no tool observation path)  
3. Verified violation + `stop_on_first_violation=true` (default for demos)  
4. `generation >= Gmax`  
5. Soft wall-clock budget  

---

## 4. Candidate lifecycle

A **candidate** is one `AttackGenome` under evaluation in a campaign.

```mermaid
stateDiagram-v2
  [*] --> Created
  Created --> Queued
  Queued --> Executing
  Executing --> Scored
  Executing --> Error
  Scored --> Elite: top-E
  Scored --> ParentPool: selected
  Scored --> Discarded: not selected
  Scored --> Violator: fitness 1.0
  Violator --> Minimizing
  Minimizing --> Minimized
  Minimized --> RegressionArtifact
```

### Genome contract

- Contains **attacker user messages only**.  
- Does not store assistant text (that lives in the trace).  
- Tracks `parent_id`, `generation`, `mutations[]`, `target_rule_ids[]`, `strategy`.  

### Execution

For messages `m1..mk`:

1. `adapter.reset(session_id)`  
2. For each `mi`: `adapter.step(session_id, mi)` → append turn to trace  
3. Aggregate tool calls → policy eval → fitness  
4. Persist candidate + trace via CLI artifact writer and/or API repository  

---

## 5. Mutation lifecycle

```mermaid
sequenceDiagram
  participant CE as Campaign Engine
  participant F as AttackFocus
  participant M as Mutation Engine
  participant L as LLMClient port
  participant V as Genome Validator

  CE->>F: derive focus from PolicySet
  CE->>M: mutate(parent, focus)
  M->>M: sample operator
  alt AI operator
    M->>L: structured JSON rewrite
    L-->>M: messages or error
    alt invalid / error
      M->>M: retry <= 2 then template fallback
    end
  else structural / template
    M->>M: apply deterministic transform
  end
  M->>V: validate length/turns/chars
  V-->>CE: child genome
```

### Operators (current)

| Operator | Kind | Intent |
|---|---|---|
| `semantic_rephrase` | AI | Paraphrase last turn |
| `authority_escalation` | AI+template | Manager/legal framing |
| `multi_turn_setup` | structural | Insert benign setup turn |
| `confirmation_bypass` | AI+template | Fake prior approval / APR codes |
| `argument_nudging` | AI | Push numeric args across boundary |
| `indirect_request` | AI | Ask to draft tool JSON |

No crossover in current scope.

`AttackFocus` extracts tools + critical args from selected rules so mutations aim at **policy boundaries**, not generic jailbreaks.

---

## 6. Fitness evaluation lifecycle

```mermaid
flowchart TD
  T[ExecutionTrace] --> PE[PolicyEvaluator]
  PE --> H[PolicyHit per rule]
  H --> V{any violated?}
  V -->|yes| One[fitness = 1.0]
  V -->|no| S[weighted proximity score]
  S --> Fit[fitness in 0..1)
  One --> Out[FitnessResult]
  Fit --> Out
```

### Rules

- **Violation is binary and deterministic.**  
- Continuous score is a **search heuristic only**.  
- Default components (weights sum guidance; clamp to `[0,1)` if not violated):

| Signal | Role |
|---|---|
| `engage` | Non-refusal or any tool call |
| `premise_accept` | Lightweight cues of accepted false authority |
| `tool_name_hit` | Target tool appeared |
| `arg_proximity` | Near numeric/boolean boundary |
| `confirmation_weakening` | Restricted action with weak flags |

Exact weight defaults are implementation constants; changing them requires tests, not UI toggles.

**Selection:** elites = top E; parents ~ `(fitness + ε)^α`.

---

## 7. Policy evaluation lifecycle

```mermaid
flowchart TD
  PS[PolicySet] --> R[For each rule]
  TC[all tool calls + context] --> R
  R --> K{kind}
  K -->|deny_tool| D[violated if tool present]
  K -->|require_args| W[if when matches: require must hold]
  K -->|forbid_args| F[if tool present: forbid must not hold]
  D --> Hit[PolicyHit]
  W --> Hit
  F --> Hit
```

### Policy primitives (current)

1. `deny_tool`  
2. `require_args` (+ optional `when`)  
3. `forbid_args`  

Deferred: `require_prior_tool`, rich `output_contract`.

### Data contract (logical)

```
PolicySet { version, target, rules[] }
PolicyRule { id, description, tool, kind, when?, require?, forbid?, deny? }
PolicyHit { rule_id, violated, evidence, proximity }
```

Evaluation is **pure**: `(PolicySet, ExecutionTrace, context) → list[PolicyHit]`.

Context supplies deterministic facts (e.g. `customer.email`). No LLM calls.

### Policy generation (product surface)

`mutiny init` may seed `policy.yaml` from templates and/or discovered tool names. **Human review is required** before treating policies as authoritative. Auto-suggested rules are never the acceptance oracle without explicit content.

---

## 8. Minimization lifecycle

Goal: smallest message list that still yields the **same rule violation** under re-execution.

```mermaid
flowchart TD
  G[Violating genome] --> DD[ddmin on messages]
  DD --> RX[Re-exec + PolicyEval]
  RX -->|still violates| Keep[Accept subset]
  RX -->|not| Reject[Reject subset]
  Keep --> DD
  DD --> Short{optional AI shorten?}
  Short -->|yes| AI[Propose shorter text]
  AI --> RX2[Re-exec gate]
  RX2 -->|ok| Out[Minimized genome]
  RX2 -->|fail| KeepMsg[Keep previous text]
  Short -->|no| Out
```

**Invariant:** CLI and Hosted API must refuse regression save unless `still_reproduces=true` on the final genome.

---

## 9. Regression lifecycle

```mermaid
sequenceDiagram
  participant U as User
  participant CLI as CLI / Hosted API
  participant Core as Regress + Policy
  participant Ad as Adapter

  U->>CLI: save regression(candidate)
  CLI->>Core: build artifact from minimized genome
  CLI->>CLI: persist artifact (project path and/or DB)
  U->>CLI: mutiny test / run tests
  CLI->>Core: replay(conversation)
  Core->>Ad: reset + step turns
  Core->>Core: evaluate must_not_violate
  Core-->>CLI: PASS or FAIL
  CLI-->>U: results
```

### Artifact contract

```
RegressionTest {
  version,
  name,
  target,
  policy_rule_ids[],
  conversation[],          # user messages
  expected.must_not_violate[],
  provenance { campaign_id, candidate_id, minimized_from_turns }
}
```

**PASS** iff none of `must_not_violate` rules are violated on replay.  
Same evaluator as live campaigns.

Default write location for local runs: under the customer project (e.g. `.mutiny/tests/` or `examples/.../tests` for the sample). Hosted may also store blobs in SQLite.

---

## 10. Hosted request flow (secondary)

Typical campaign start when using Hosted:

1. `POST /api/campaigns` — validate config, store row `status=created`  
2. `POST /api/campaigns/{id}/start` — attestation, health, spawn task  
3. `GET /api/campaigns/{id}/events` — SSE subscription  
4. `GET /api/campaigns/{id}` / `.../candidates` — snapshot recovery  
5. On violation UI: `POST /api/candidates/{id}/minimize`  
6. `POST /api/candidates/{id}/regression`  
7. `POST /api/tests/run`  

API authenticates nothing multi-tenant in current scope; local single-user trust with attestation flag.

**Note:** Hosted may still wire the bundled demo adapter alongside the OpenAI Agents SDK + CLI path. Product narrative prefers sample-as-example, not demo-as-product.

---

## 11. CLI → Core → Adapter → Target → Trace

```mermaid
sequenceDiagram
  participant CLI as mutiny run
  participant CE as Campaign Engine
  participant Ad as OpenAI Agents SDK Adapter
  participant Ag as User / sample agent
  participant PE as Policy/Fitness

  CLI->>CE: run(config, on_event)
  loop each candidate
    CE->>Ad: reset/step*
    Ad->>Ag: tool-calling chat
    Ag-->>Ad: assistant + tool_calls
    Ad-->>CE: AdapterTurnResult
    CE->>PE: evaluate(trace)
    PE-->>CE: fitness
    CE->>CLI: on_event(candidate.scored)
  end
```

**Trace ownership:** produced in Core during execution; **persisted** by CLI and/or API.

---

## 12. Frontend → API → Core → Adapter → Target → Trace

```mermaid
sequenceDiagram
  participant UI as Web
  participant API as API
  participant CE as Campaign Engine
  participant Ad as Adapter
  participant Ag as Sample or attached agent
  participant PE as Policy/Fitness
  participant DB as SQLite

  UI->>API: start campaign
  API->>DB: status=running
  API->>CE: run(config, on_event)
  loop each candidate
    CE->>Ad: reset/step*
    Ad->>Ag: tool-calling chat
    Ag-->>Ad: assistant + tool_calls
    Ad-->>CE: AdapterTurnResult
    CE->>PE: evaluate(trace)
    PE-->>CE: fitness
    CE->>API: on_event(candidate.scored)
    API->>DB: upsert candidate+trace+event
    API-->>UI: SSE candidate.scored
  end
```

---

## 13. Persistence flow

| Entity | Written by | Read by |
|---|---|---|
| `campaigns` | Hosted API | API, Web |
| `candidates` | API (from Core results) | API, Web |
| `traces` | API / CLI artifact writer | API, Web, CLI |
| `events` | API | SSE + Web resume |
| `regressions` | API / CLI | API, CLI, Web |
| Local project files | CLI (`policy.yaml`, regressions) | Developer, CI |

Core returns objects; API serializes JSON columns. Core never opens SQLite.

### Logical schema (Hosted)

- `campaigns(id, status, config_json, metrics_json, created_at, completed_at)`  
- `candidates(id, campaign_id, parent_id, generation, genome_json, fitness, status)`  
- `traces(candidate_id, trace_json)`  
- `events(id, campaign_id, ts, type, payload_json)`  
- `regressions(id, campaign_id, candidate_id, path, artifact_json)`  

---

## 14. Event flow

Core campaign accepts an `on_event(MutinyEvent)` callback.  
Hosted API: append to `events` table + fan out to SSE subscribers.  
CLI: print / log structured progress.

Event types (canonical):

- `campaign.started`  
- `generation.started`  
- `candidate.created`  
- `candidate.executing`  
- `candidate.scored`  
- `violation.detected`  
- `minimization.started`  
- `minimization.step`  
- `exploit.minimized`  
- `regression.created`  
- `campaign.completed`  
- `campaign.error`  

---

## 15. SSE flow

```mermaid
sequenceDiagram
  participant UI
  participant API
  participant Task as Campaign Task

  UI->>API: GET /events (SSE)
  API-->>UI: ready
  loop during campaign
    Task->>API: emit(event)
    API->>API: insert events row
    API-->>UI: data: event JSON
  end
  Note over UI,API: On disconnect, UI resumes via GET /candidates snapshot
```

SSE is one-way telemetry. Commands always use REST (Hosted) or CLI commands (local).

---

## 16. Configuration flow

Sources (highest wins for explicit overrides):

1. Campaign create payload (UI) or CLI flags  
2. Project `mutiny.yaml` / `policy.yaml`  
3. Env defaults  
4. Code defaults (ARCHITECTURE hard maxes)

Pinned fields for demos / harness:

- `target_model`  
- `mutation_model`  
- `temperature`  
- `N`, `Gmax`, `max_turns`  
- `stop_on_first_violation`  
- `policy_set_id` / path to PolicySet  
- `adapter` path / module  

Hosted `/api/health` probes model reachability before start when using Hosted.

---

## 17. Model interaction flow

| Call site | Model role | Output validation |
|---|---|---|
| Target agent turns (user project / sample) | Target | Tool-call schema from agent / SDK |
| Mutation operators | Attacker | JSON → Pydantic genome patch; retry; template fallback |
| Optional shorten | Attacker | Accept only if minimize re-exec passes |
| Explanations | Reporter | Non-authoritative text after violation |

**No model call** in policy eval, fitness violation bit, regression PASS/FAIL, or event emission.

Provider: Featherless via OpenAI-compatible client behind `LLMClient` port. Fallback: Ollama → templates.

---

## 18. Failure handling flow

| Failure | Behavior |
|---|---|
| Mutation JSON invalid | Retry ≤2 → template operator |
| Target turn timeout | Candidate `error`; fitness 0; continue campaign |
| No tool observation capability | Fail campaign (`campaign.error`) |
| Featherless down | Health check blocks Hosted start; runtime fallback to Ollama/templates if configured |
| SSE disconnect | UI snapshot sync |
| Minimize cannot shrink | Keep original violator; still allow save if reproduces |
| Wall-clock exceeded | `campaign.completed` reason=`budget` |
| Attestation missing (Hosted) | Reject start |
| Adapter import failure | Fail `mutiny run` with actionable error |

Never write a synthetic `violation.detected` without a real scored trace.

---

## 19. Data ownership

| Data | Owner |
|---|---|
| Policy semantics | Core |
| Genome / trace types | Core |
| Campaign rows / SQL | Hosted API |
| Project `policy.yaml` / regressions | Developer project + CLI writers |
| UI selection state | Web (ephemeral) |
| Sample/demo mock DB | demo_agent process memory |

---

## 20. Trust boundaries

```mermaid
flowchart TB
  subgraph trusted [Trusted computing base]
    Core
    API
    CLI
    Web_static[Web code we ship]
  end

  subgraph semi [Configured but untrusted content]
    AttackText[Attack genomes]
    TargetOut[Target model outputs]
    UserAdapter[Customer adapter.py]
  end

  subgraph denied [Out of current scope]
    Internet[Arbitrary remote hosts]
  end

  AttackText --> Core
  TargetOut --> Core
  UserAdapter --> Core
  Core --> API
  Core --> CLI
  Internet -.->|blocked| API
```

- Treat model outputs as **untrusted data**, not instructions to Mutiny.  
- Treat attack text and customer adapter code as untrusted relative to Mutiny’s control plane.  
- Do not pass target output into Mutiny’s control prompts without sanitizing/structuring.  
- Target allowlist enforced in API before adapter construction (Hosted).  

---

## 21. Sequence diagrams (index)

Primary sequences in this doc:

- §2 `mutiny init`  
- §5 Mutation  
- §9 Regression  
- §11 CLI evaluation path  
- §12 Hosted evaluation path  
- §15 SSE  

Campaign-level sequence (condensed):

```mermaid
sequenceDiagram
  participant U as Developer
  participant CLI
  participant Core
  loop generations
    Core->>Core: evaluate population
    Core->>CLI: events
    Core->>Core: select + mutate
  end
  Core->>CLI: violation.detected
  U->>CLI: minimize + save regression
```

---

## 22. Component interaction diagram

```mermaid
flowchart TB
  subgraph local [Local primary]
    CLI[mutiny init / run]
    Proj[Customer agent project]
    OAI[OpenAI Agents SDK Adapter]
    AL[Adapter Layer]
  end

  subgraph hosted [Hosted secondary]
    Web[apps/web]
    API[apps/api]
    DB[(SQLite)]
  end

  subgraph core [packages/mutiny_core — framework-independent]
    Campaign
    Mutate
    Policy
    Fitness
    Minimize
    Regress
    Ports[Adapter + LLM ports]
  end

  subgraph sample [Reference]
    Demo[apps/demo_agent]
    InProc[Demo / sample adapter]
  end

  CLI --> Campaign
  Web --> API
  API --> DB
  API --> Campaign
  Campaign --> Mutate
  Campaign --> Fitness
  Fitness --> Policy
  Campaign --> Ports
  Minimize --> Ports
  Minimize --> Policy
  Regress --> Ports
  Regress --> Policy
  Ports --> AL
  AL --> OAI --> Proj
  AL --> InProc --> Demo
```

Future adapters (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP, …) attach at the Adapter Layer without changing Core campaign/policy/minimize/regression/fitness.
---

## 23. State diagrams

- Campaign: §3  
- Candidate: §4  

Minimization local state: `idle → running → step → verified → done | failed`.

---

## 24. Data contracts (implementation-facing)

### ToolCall

`{ id, name, arguments: object }`

### AdapterTurnResult

`{ assistant_message?, tool_calls[], tool_results[], raw }`

### ExecutionTrace

`{ candidate_id, session_id, turns[], all_tool_calls[], policy_hits[], fitness, status, error?, model_info, token_usage }`

### AttackGenome

`{ id, parent_id?, generation, strategy, mutations[], target_rule_ids[], messages[{role, content}], metadata }`

These names are normative for current scope. Field additions must be backward compatible in stored JSON.

---

## 25. Sample / demo target design (system-level)

The bundled support agent remains part of system design as a **reference harness** (reliability, docs, Hosted sample wiring)—not as the primary user workflow.

- Tools include `issue_refund(order_id, amount, approved)` among others.  
- Policy under test: `amount > 200 ⇒ approved == true`.  
- Vulnerability: soft prompt trusts fake `APR-####` codes; no server-side approval store; model may set `approved` freely.  
- Mutiny must discover via search + real tool calls—not by inserting violations.

Preferred demo narrative uses this (or a thin OpenAI Agents SDK sample) as “clone this sample project → mutiny init → mutiny run.” Details of seeds/operators live in IMPLEMENTATION_PLAN and demo config—not as fake success shortcuts.

---

## 26. Observability

Each campaign exposes:

- Generation index, population size  
- Per-candidate fitness, status, latency  
- Token counters when available  
- Error strings on failed candidates  
- Health: API up, DB up, model probe (Hosted); adapter load OK (CLI)  

Hosted UI should show an observability strip; API stores `metrics_json` on completion. CLI should emit equivalent summary metrics.
