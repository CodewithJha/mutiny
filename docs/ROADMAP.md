# Mutiny — Roadmap

| Field | Value |
|---|---|
| **Status** | Canonical phased roadmap |
| **Last updated** | 2026-09-09 |
| **Rule** | Do not mix future work into current-scope execution. Near-term detail lives in [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md). Production Hosted gates: [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md). |

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
- **M-PR2:** CLI `mutiny run` defaults to local Core; Hosted requires `--hosted` / `--hosted-url` (config URL alone never selects Hosted)  
- **M-PR1:** Hosted customer `project_path` adapter execution disabled by default (`MUTINY_ALLOW_PROJECT_EXEC=1` opt-in; trusted `in_process_demo` only otherwise)  
- **M-PR7:** Optional single-tenant Hosted Bearer auth (`MUTINY_API_TOKEN`); not multi-tenant / not a sandbox  
- **ADR-019 (accepted decision; M-PR8 in progress):** Hosted observe/lineage for customer projects; customer adapter exec on Local CLI — ingest API + CLI sync shipped (M-PR8B/C); remove production exec still pending (M-PR8E)  
- **M-PR8A (docs):** CLI → Hosted ingestion contract defined in [HOSTED_INGESTION.md](./HOSTED_INGESTION.md)
- **M-PR8B (server):** Hosted `/api/ingest/v1/*` observe-only ingest shipped  
- **M-PR8C (CLI):** `mutiny run --hosted` = local Core + end-of-run ingest sync 
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
- **M-PR8 (in progress):** Implement ADR-019 observe-only Hosted — **8A–C** done (contract, ingest API, CLI sync); **8D/E** Web copy / remove production customer `exec_module`

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
- Skills published for common coding-agent workflows  

---

## 4. v1

- Authenticated single-tenant Hosted deploy  
- Ownership attestation for remote targets  
- Hosted observe/lineage ingest per ADR-019 (after M-PR8)  
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
