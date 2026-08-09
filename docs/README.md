# Mutiny Documentation

**All project documentation lives in this directory.** The repository root only points here.

**Mutiny is a behavioral fuzz-testing engine for AI agents.** Developers install it into their own agent project via an adapter:

> `mutiny init` → connect adapter → `mutiny run` → search for policy breaks → prove on traces → minimize → save permanent regression tests.

**What's included today:** OpenAI Agents SDK projects through Adapter #1. Bundled/sample agents are reference harnesses, not the primary product. See [ADR-017](./DECISION_LOG.md#adr-017--customer-owned-local-projects-primary-bundled-demo-secondary) and [ADR-018](./DECISION_LOG.md#adr-018--adapter-first-architecture).

These documents are the **source of truth for implementation**. Prefer updating docs before changing architecture in code.

**Safety:** Authorized testing only. Current targets are local projects / in-process / localhost with sandboxed mock tools for demos.

**Status:** Engine-first + customer-project primary. The monorepo `uv` path is supported today; PyPI publish is on the roadmap. See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) and [COLD_START.md](./COLD_START.md).

## Document map

| Document | Owns | Does not own |
|---|---|---|
| [PRD.md](./PRD.md) | Product intent, users, requirements, non-goals | Algorithms, package layout, day-by-day tasks |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Principles, layering, package ownership, constraints | Product roadmap, competitor detail |
| [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) | Lifecycles, data contracts, flows, diagrams | Milestone scheduling, demo narration |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Milestones, DoD, sequencing | Product vision, long-term roadmap |
| [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) | Live demo scripts, backup, Q&A | System internals |
| [COLD_START.md](./COLD_START.md) | Clean-machine bootstrap + smoke gate | Product narrative |
| [DEVPOST.md](./DEVPOST.md) | Short public submission / pitch copy | Live demo choreography |
| [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md) | Competitive landscape (claims freeze) | Mutiny feature specs |
| [DECISION_LOG.md](./DECISION_LOG.md) | Architecture Decision Records | Ongoing task lists |
| [ROADMAP.md](./ROADMAP.md) | Phased future work | Near-term execution detail |
| [DESIGN.md](./DESIGN.md) | Pointer to Hosted visual canon | Product requirements |

## Conflict resolution

1. **Product intent** → PRD  
2. **Hard engineering constraints / boundaries** → ARCHITECTURE  
3. **Behavioral contracts (how the system works)** → SYSTEM_DESIGN  
4. **What to build next / DoD** → IMPLEMENTATION_PLAN  
5. **Why we chose X** → DECISION_LOG  

If docs disagree, fix the docs in that order—do not silently pick a convenient interpretation in code.

## Reading order (new engineer)

1. PRD (thesis + non-goals)  
2. ARCHITECTURE (boundaries)  
3. SYSTEM_DESIGN (how it runs)  
4. IMPLEMENTATION_PLAN (milestones — note honest DoD)  
5. DECISION_LOG (context, especially ADR-017 / ADR-018)  
6. DEMO_SCRIPT / COMPETITOR_ANALYSIS / ROADMAP as needed  

## Product shape (canonical)

```
Customer agent project
        ↑
OpenAI Agents SDK Adapter   ← Adapter #1 (shipped)
        ↑
   Adapter Layer            ← future: LangGraph, CrewAI, PydanticAI, AutoGen, HTTP, …
        ↑
   Mutiny Core              ← behavioral fuzz-testing engine
        ↑
   CLI (mutiny init / run)  ← primary
   Hosted API + UI          ← secondary
   Sample / demo agent      ← reference harness
```
