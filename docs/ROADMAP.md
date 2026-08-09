# Mutiny — Roadmap

| Field | Value |
|---|---|
| **Status** | Canonical phased roadmap |
| **Last updated** | 2026-08-09 |
| **Rule** | Do not mix future work into current-scope execution. Near-term detail lives in [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md). |

---

## 1. Current scope

**Goal:** Mutiny as a **behavioral fuzz-testing engine** installable into a developer’s agent project: init → run → prove → minimize → regress. Adapter #1 = **OpenAI Agents SDK**. Hosted UI optional for lineage. Bundled/sample agent is a **reference**, not the product.

**What's included:**

- Mutiny Core search + deterministic policy oracle (framework-independent)  
- **Adapter #1: OpenAI Agents SDK only**  
- CLI: `mutiny init` / `mutiny run` (+ regression replay)  
- Sample / demo project as docs example + reliability harness  
- Hosted API + SSE + campaign UI (secondary)  
- Minimize + regression save/replay  
- Safety binds (local/in-process/localhost, attestation)  
- Reliability smoke (≥2/3 on harness)  
- Docs matching engine-first + customer-project primary  

**Limitations / out of scope (explicit):**

- LangGraph, CrewAI, PydanticAI, AutoGen, HTTP adapters (Beta/v1 — same interface)  
- MCP (unless stretch after green)  
- Multi-tenant cloud  
- Broad repo scanning  
- Open-internet targets  
- Postgres/K8s/queues  
- Treating bundled demo as the primary user workflow  
- Defining Mutiny as an OpenAI Agents SDK testing tool  

**Exit:** See IMPLEMENTATION_PLAN milestones under the customer-project narrative.

---

## 2. Next (after current OSS baseline)

- Keep PyPI packages (`mutiny-ai` / `mutiny-core` / `mutiny-openai-agents`) version-aligned on each release
- Keep demo assets under `docs/assets/` current with Hosted UI
- Keep good-first-issue queue fresh ([GOOD_FIRST_ISSUES.md](./GOOD_FIRST_ISSUES.md))
- Clarify sample vs customer-project paths in UX copy as adapters land

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

Ideas that must not leak into current scope:

- Vector attack memory  
- NL policies judged solely by LLMs  
- Universal static analysis across all agent frameworks  
- Unrestricted public attack proxy  
- Enterprise SSO/billing  
- Shipping five framework adapters “for the README”  

Promote from parking lot only via ADR + ROADMAP stage change.
