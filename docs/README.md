# Mutiny Documentation

**All project documentation lives here.** The [root README](../README.md) is the
public front door; this hub is the source of truth for product intent, architecture,
and contributor onboarding.

**Mutiny** is a behavioral fuzz-testing engine for AI agents. Install it into
**your** agent project via an adapter:

> `mutiny init` → connect adapter → `mutiny run` → search for policy breaks → prove on traces → minimize → save permanent regression tests.

**Shipped today:** Adapter #1 — **OpenAI Agents SDK**. Install **from source**
(`uv sync --extra dev`); PyPI publish is on the roadmap. Sample/demo agents are
**reference harnesses**, not the primary product.

**Safety:** Authorized testing only. Targets are local / in-process / localhost
with sandboxed mock tools for demos.

---

## Start here

| If you want… | Read |
|---|---|
| Install + try in 5 minutes | [Root README](../README.md) |
| Clean-machine bootstrap | [COLD_START.md](./COLD_START.md) |
| Contribute / first PR | [CONTRIBUTING.md](../CONTRIBUTING.md) · [GOOD_FIRST_ISSUES.md](./GOOD_FIRST_ISSUES.md) |
| Architecture boundaries | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| How the system runs | [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) |
| What’s next | [ROADMAP.md](./ROADMAP.md) |
| Why we chose X | [DECISION_LOG.md](./DECISION_LOG.md) (esp. ADR-017, ADR-018) |
| Support / security | [SUPPORT.md](../SUPPORT.md) · [SECURITY.md](../SECURITY.md) |

---

## Document map

| Document | Owns | Does not own |
|---|---|---|
| [PRD.md](./PRD.md) | Product intent, users, requirements, non-goals | Algorithms, package layout, day-by-day tasks |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Principles, layering, package ownership, constraints | Product roadmap, competitor detail |
| [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) | Lifecycles, data contracts, flows, diagrams | Milestone scheduling, demo narration |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Milestones, DoD, sequencing | Product vision, long-term roadmap |
| [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) | Live demo scripts, backup, Q&A | System internals |
| [COLD_START.md](./COLD_START.md) | Clean-machine bootstrap + smoke gate | Product narrative |
| [GOOD_FIRST_ISSUES.md](./GOOD_FIRST_ISSUES.md) | Catalog of small contributor tasks | Execution ownership of Core redesigns |
| [DEVPOST.md](./DEVPOST.md) | Short public pitch copy | Live demo choreography |
| [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md) | Competitive landscape (claims freeze) | Mutiny feature specs |
| [DECISION_LOG.md](./DECISION_LOG.md) | Architecture Decision Records | Ongoing task lists |
| [ROADMAP.md](./ROADMAP.md) | Phased future work | Near-term execution detail |
| [DESIGN.md](./DESIGN.md) | Pointer to Hosted visual canon | Product requirements |

Community files at repo root: [CONTRIBUTING](../CONTRIBUTING.md),
[CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md), [SECURITY](../SECURITY.md),
[SUPPORT](../SUPPORT.md), [LICENSE](../LICENSE).

---

## Conflict resolution

1. **Product intent** → PRD  
2. **Hard engineering constraints / boundaries** → ARCHITECTURE  
3. **Behavioral contracts (how the system works)** → SYSTEM_DESIGN  
4. **What to build next / DoD** → IMPLEMENTATION_PLAN  
5. **Why we chose X** → DECISION_LOG  

If docs disagree, fix the docs in that order—do not silently pick a convenient interpretation in code.

**Install claims:** Prefer the root README. Today that means **git + `uv sync`**, not `pip install mutiny` (planned). Pitch docs that still show PyPI should say “planned.”

---

## Reading order (new engineer)

1. Root [README](../README.md) (What / Why / Install / Try)  
2. [PRD.md](./PRD.md) (thesis + non-goals)  
3. [ARCHITECTURE.md](./ARCHITECTURE.md) (boundaries)  
4. [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) (how it runs)  
5. [DECISION_LOG.md](./DECISION_LOG.md) (ADR-017 customer-project primary; ADR-018 adapter-first)  
6. [ROADMAP.md](./ROADMAP.md) / [GOOD_FIRST_ISSUES.md](./GOOD_FIRST_ISSUES.md) as needed  

---

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
   CLI (mutiny init / run / test)  ← primary
   Hosted API + UI                 ← secondary
   Sample / demo agent             ← reference harness
```

Screenshots / demo assets: place under `docs/assets/` (see README Screenshots section). Suggested files: `cli-run.png`, `hosted-campaign.png`, `policy-yaml.png`.
