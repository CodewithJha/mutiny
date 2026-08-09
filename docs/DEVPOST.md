# Mutiny — Devpost submission

Paste / adapt into Devpost. Keep claims honest; freeze competitive wording to COMPETITOR_ANALYSIS. Align with [ADR-017](./DECISION_LOG.md#adr-017--customer-owned-local-projects-primary-bundled-demo-secondary) and [ADR-018](./DECISION_LOG.md#adr-018--adapter-first-architecture).

---

## Tagline
AFL for AI agent tool policies — a behavioral fuzz-testing engine you install into your agent, find the break, prove it on the tool call, lock it as a test.

## Elevator (15 seconds)
AI agents don’t just chat — they call tools that move money and change accounts. Prompts aren’t tests. **Mutiny** is a behavioral fuzz-testing engine for AI agents: `pip install mutiny` → `mutiny init` → `mutiny run`. The Hackathon MVP ships with support for OpenAI Agents SDK projects through the first adapter. It searches until your agent breaks an explicit rule (e.g. refunds over $200 need approval), shows the **real tool-call JSON** as proof, minimizes the conversation, and saves a regression that FAIL→PASS when you fix the agent.

## The problem
System prompts say “be careful with refunds.” Agents still do:
`issue_refund({ amount: 210, approved: false })`.
That’s a **software defect in action policy**, invisible to chat-quality evals — and you need to find it in **the agent you ship**, not only in someone else’s demo.

## What we built
**Mutiny** — a behavioral fuzz-testing engine for AI agents:

1. **Install** into your project (`mutiny init` → adapter + `policy.yaml` + `mutiny.yaml`)  
2. **Search** with an evolutionary campaign against *your* agent via adapter  
3. **Prove** with a deterministic PolicyEvaluator on execution traces (AI proposes; **code proves**)  
4. **Minimize** with re-execution until it still breaks  
5. **Regress** — save forever; vulnerable agent FAIL, fixed agent PASS  

Optional **Hosted UI** shows live lineage. A bundled **sample** agent is a reference harness / docs example — not the product.

**MVP scope:** Adapter #1 = OpenAI Agents SDK (other frameworks = future adapters on the same Core).

**Safety:** authorized use; local / localhost; **mock tools** in demos (no live bank). The tool call is real; side effects are sandboxed.

## Demo path (judges)
1. Clone / open a sample agent project (MVP: OpenAI Agents SDK)  
2. `mutiny init` → show adapter + `refund_limit` policy  
3. `mutiny run` → **Policy broken · real tool call** with JSON  
4. Minimize → Save regression  
5. Optional Hosted: lineage graph  
6. Tests → vulnerable FAIL → fixed PASS  

Backup: `scripts/backup_fixture_demo.py` + smoke gate `scripts/smoke_reliability.py` (≥2/3). If CLI surfaces are still landing, demo the same loop on the sample harness and state the install path clearly.

## Tech
- **Python:** Mutiny Core (oracle, campaign, minimize, regress — framework-independent) + OpenAI Agents SDK adapter (Adapter #1)  
- **CLI:** `mutiny init` / `mutiny run`  
- **FastAPI + SQLite + SSE:** Hosted API (secondary)  
- **Next.js:** Hosted UI (secondary)  
- **Featherless (optional):** mutation LLM; offline **template search** for reliability when no key is set  

## What’s next
LangGraph / CrewAI / PydanticAI / AutoGen / HTTP adapters on the same interface; CLI / CI beat; MCP/Skills. Not an open proxy to the public internet.

## Challenges
Making search reliable without faking violations; keeping the oracle LLM-free; pivoting from demo-harness to customer-project install without overclaiming; explaining sandbox vs simulation without losing trust.

## Closing line
Mutiny doesn’t ask whether your agent *looks* safe. It keeps attacking until it proves where your policy breaks — then makes sure that failure never comes back.
