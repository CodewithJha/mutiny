# Mutiny

_Define what your agent must never do. Then prove it can't._

**Mutiny is a behavioral fuzz-testing engine for AI agents.**

You install it into your agent project, write tool-use policies, and Mutiny searches for conversations that break them — then proves the break on a tool-call trace, minimizes it, and freezes it as a regression test.

Hackathon MVP ships **Adapter #1: OpenAI Agents SDK**. Same Core; more adapters later ([roadmap](./docs/ROADMAP.md)).

**Docs:** [`docs/`](./docs/) — start at [`docs/README.md`](./docs/README.md).

---

You ship an agent that refunds money, deletes accounts, sends email. Your system prompt says “be careful.” Attackers don’t care about your system prompt.

What actually fails looks like this:

```json
issue_refund({ "amount": 850, "approved": false })
delete_account({ "confirmed": false })
```

That’s not a bad answer. That’s a **policy break in action** — and most eval stacks never see it.

Mutiny treats those invariants like fuzz targets: search, prove, minimize, regress.

## How it works

```
1. Connect your agent     → adapter (MVP: OpenAI Agents SDK)
2. Declare invariants     → policy.yaml (deterministic tool rules)
3. Search                 → evolutionary campaign mutates attack conversations
4. Prove                  → code evaluates tool calls on the trace (not an LLM judge)
5. Minimize               → smallest reproduction that still violates
6. Freeze                 → permanent regression under .mutiny/tests/
```

**AI proposes. Code proves.**

```
Your agent project
        ↑
OpenAI Agents SDK Adapter   ← Adapter #1 (MVP)
        ↑
   Adapter Layer            ← future: LangGraph, CrewAI, PydanticAI, AutoGen, HTTP, …
        ↑
   Mutiny Core              ← framework-independent engine
        ↑
   CLI (init / run / test)  ← primary
   Hosted API + UI          ← secondary (lineage / ops)
```

## Quick start

This repo is a **uv monorepo**. That’s the path that works today.

### 1. Bootstrap the monorepo

```bash
# Prerequisites: Python ≥ 3.11, uv
git clone https://github.com/CodewithJha/mutiny.git
cd mutiny
uv sync --extra dev
```

This installs Core, the OpenAI Agents SDK adapter, and the `mutiny` CLI into the workspace.

### 2. Point Mutiny at an agent project

**Sample project (recommended first run):**

```bash
cd examples/openai_support_agent
uv run mutiny init    # scaffolds .mutiny/adapter.py, policy.yaml, mutiny.yaml
uv run mutiny run --no-hosted
uv run mutiny test    # replay saved regressions (after a finding is saved)
```

**Your own OpenAI Agents SDK project:**

```bash
cd /path/to/your-agent
# from the Mutiny checkout, with the workspace env active — or install the packages editable
uv run --directory /path/to/mutiny mutiny init --path .
# edit .mutiny/adapter.py → AGENT_REF + POLICY_CONTEXT
# edit policy.yaml        → your tool names and rules
uv run --directory /path/to/mutiny mutiny run --path . --no-hosted
uv run --directory /path/to/mutiny mutiny test --path .
```

`mutiny init` writes:

| File | Role |
|---|---|
| `.mutiny/adapter.py` | Wires Adapter #1 to your agent export |
| `policy.yaml` | Deterministic tool-use invariants |
| `mutiny.yaml` | Campaign defaults |

### 3. Optional: Hosted UI

For campaign lineage and evidence in a browser:

```bash
# from repo root
./scripts/dev.sh
# API :8000 · UI http://127.0.0.1:3000
```

Then `mutiny run` (without `--no-hosted`) prefers the Hosted API when reachable.

## Commands

| Command | What it does |
|---|---|
| `mutiny init` | Scaffold adapter stub + `policy.yaml` + `mutiny.yaml` |
| `mutiny run` | Load adapter + policy; run a campaign; minimize / save regressions |
| `mutiny test` | Replay regressions under `.mutiny/tests/` (PASS / FAIL / SKIPPED) |

## What’s included

| | |
|---|---|
| **Mutiny Core** | Policy oracle, campaign loop, fitness, minimize, regression replay |
| **Adapter #1** | OpenAI Agents SDK → your local agent |
| **CLI** | `mutiny init` / `run` / `test` |
| **Sample project** | [`examples/openai_support_agent/`](./examples/openai_support_agent/) |
| **Hosted** | Optional API + UI for lineage (secondary) |
| **Demo harness** | Bundled demo agent used as a reference / reliability target |

| Not in MVP | |
|---|---|
| LangGraph / CrewAI / PydanticAI / AutoGen / HTTP adapters | [Roadmap](./docs/ROADMAP.md) |
| PyPI `pip install mutiny` as the primary install | Planned; monorepo `uv` is the working path now |
| Open-internet attack proxy | Out of scope |

## Develop (contributors)

```bash
uv sync --extra dev
uv run pytest tests/ -q

# Reliability smoke against the interim demo harness (≥2/3)
PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \
  uv run python scripts/smoke_reliability.py

./scripts/dev.sh   # Hosted API + UI
```

Cold start: [`docs/COLD_START.md`](./docs/COLD_START.md) · Architecture: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · System design: [`docs/SYSTEM_DESIGN.md`](./docs/SYSTEM_DESIGN.md).

## Status

Hackathon MVP in progress. Product thesis is engine-first + customer project via adapter ([ADR-017](./docs/DECISION_LOG.md#adr-017--customer-owned-local-projects-primary-bundled-demo-secondary), [ADR-018](./docs/DECISION_LOG.md#adr-018--adapter-first-architecture)). Hosted still also exercises a bundled demo agent as an interim harness — useful for demos, not the primary user story.

## Safety

Authorized testing only. MVP targets are local projects / in-process or localhost with sandboxed mock tools. Mutiny is not an open-internet attack proxy.

## License

License TBD (not yet applied in-repo).
