# Mutiny — Roadmap

| Field | Value |
|---|---|
| **Status** | Canonical phased roadmap |
| **Last updated** | 2026-08-07 |
| **Rule** | Do not mix future work into MVP execution. MVP detail lives in [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md). |

---

## 1. Hackathon MVP (now)

**Goal:** Ship Mutiny as a **behavioral fuzz-testing engine** installable into a developer’s agent project: init → run → prove → minimize → regress. Hackathon MVP Adapter #1 = **OpenAI Agents SDK**. Hosted UI optional for lineage. Bundled/sample agent is a **reference**, not the product.

In scope:

- Mutiny Core search + deterministic policy oracle (framework-independent)  
- **Adapter #1: OpenAI Agents SDK only**  
- CLI: `mutiny init` / `mutiny run` (+ regression replay P1)  
- Sample / demo project as docs example + reliability harness  
- Hosted API + SSE + campaign UI (secondary)  
- Minimize + regression save/replay  
- Safety binds (local/in-process/localhost, attestation)  
- Reliability smoke (≥2/3 on harness)  
- Docs matching engine-first + customer-project primary  

Out of scope (explicit):

- LangGraph, CrewAI, PydanticAI, AutoGen, HTTP adapters (Beta/v1 — same interface)  
- MCP (unless stretch after green)  
- Multi-tenant cloud  
- Broad repo scanning  
- Open-internet targets  
- Postgres/K8s/queues  
- Treating bundled demo as the primary user workflow  
- Defining Mutiny as an OpenAI Agents SDK testing tool  

**Exit:** See IMPLEMENTATION_PLAN milestone “Demo” (M8) under the new narrative.

---

## 2. Post Hackathon (cleanup + OSS hygiene)

- Public README aligned to PRD (`pip install` / init / run; engine-first pitch)  
- License chosen and applied  
- Package publish story for `mutiny`  
- Recorded demo + screenshots  
- Issue templates; “good first issues” on operators/adapters  
- Retire Iris-only sharp edges without breaking the thesis  
- Clarify sample vs customer-project paths in UX copy  

---

## 3. Beta

New adapters on the **same** `TargetAdapter` interface (Core unchanged):

- **LangGraph** adapter  
- **CrewAI** adapter  
- **PydanticAI** adapter  
- Localhost OpenAI-compatible **HTTP endpoint adapter** with token gate  
- Multi-campaign history UX  
- Policy editor (still deterministic primitives)  
- Exportable finding reports  
- Second reference target template  
- MCP server wrapping Hosted API / Core  
- Skills published for Cursor / Claude Code / Codex-shaped workflows  

---

## 4. v1

- Authenticated single-tenant Hosted deploy  
- Ownership attestation for remote targets  
- Stable public Core/API/CLI contracts  
- Policy packs library  
- CI token + GitHub Action for regression replay  
- **AutoGen** adapter + additional adapters as demand warrants (still one Core)  
- Postgres optional when SQLite concurrency hurts  

---

## 5. Long-term vision

- Team workspaces and org policy governance  
- Parallel campaign workers with isolation  
- Broader connector ecosystem (MCP-native targets, further frameworks) — selective  
- Complementary interop with Promptfoo/Garak where useful  
- Research: better proximity signals without logits  
- Ecosystem of policy packs + adapters—not a second kernel  

**North star:** “We have a system prompt for that” is no longer an acceptable substitute for executable agent action tests **on the agent you ship**.

---

## 6. Explicit parking lot

Ideas that must not leak into MVP:

- Vector attack memory  
- NL policies judged solely by LLMs  
- Universal static analysis across all agent frameworks  
- Unrestricted public attack proxy  
- Enterprise SSO/billing  
- Shipping five framework adapters “for the README”  

Promote from parking lot only via ADR + ROADMAP stage change.
