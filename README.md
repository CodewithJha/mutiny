# Mutiny

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/CodewithJha/mutiny/actions/workflows/ci.yml/badge.svg)](https://github.com/CodewithJha/mutiny/actions/workflows/ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)
[![GitHub issues](https://img.shields.io/github/issues/CodewithJha/mutiny)](https://github.com/CodewithJha/mutiny/issues)

**Behavioral fuzz-testing for AI agents.**  
_Define what your agent must never do. Then prove it can't._

Mutiny installs into your agent project, takes deterministic **tool-use policies**, and searches for conversations that break them. When it finds a break, it **proves** it on a tool-call trace (not an LLM judge), **minimizes** the reproduction, and freezes it as a **regression test**.

Adapter #1 ships today: **OpenAI Agents SDK**. Same Core for every future adapter — contributions welcome.

```bash
uv sync --extra dev
cd examples/openai_support_agent
uv run mutiny init && uv run mutiny run --no-hosted && uv run mutiny test
```

---

## Table of contents

- [Why Mutiny](#why-mutiny)
- [Features](#features)
- [Demo](#demo)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Adapters](#adapters)
- [Commands](#commands)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [Safety](#safety)
- [License](#license)

---

## Why Mutiny

You ship an agent that refunds money, deletes accounts, sends email. Your system prompt says “be careful.” Attackers — and ordinary users — don’t care about your system prompt.

What actually fails looks like this:

```json
issue_refund({ "amount": 850, "approved": false })
delete_account({ "confirmed": false })
```

That’s not a bad answer. That’s a **policy violation in action** — and most eval stacks never see it.

Mutiny is built for **AI agent testing** that treats tool-call invariants like fuzz targets:

| Pain | What Mutiny does |
|---|---|
| Prompt-only “safety” | Executable **policy** rules on real tool args |
| LLM-as-judge flakiness | **Code proves** violations on the trace |
| One-off red-team chats | Evolutionary **behavioral fuzzing** + minimize |
| “We fixed it… maybe” | Frozen **regression testing** under `.mutiny/tests/` |

Keyword-shaped, product-shaped: agent safety, tool-call verification, OpenAI Agents SDK projects, regression suites you can replay in CI.

---

## Features

- **Policy-as-code** — Declare tool-use invariants in `policy.yaml` (deterministic operators, not vibes).
- **Behavioral fuzzing** — Evolutionary search mutates attack conversations against your live agent path.
- **Proof on traces** — Violations are evaluated in code on tool-call JSON — **AI proposes, code proves**.
- **Minimize + regress** — Smallest reproduction, saved under `.mutiny/tests/`, replayed with `mutiny test`.
- **Adapter-first Core** — Framework-independent engine; OpenAI Agents SDK adapter shipped; more via contributions.
- **CLI-first DX** — `mutiny init` / `run` / `test` into *your* project (not “host our demo agent” as the product).
- **Optional Hosted UI** — Campaign lineage and evidence when you want a browser (`./scripts/dev.sh`).

---

## Demo

No polished GIF in-repo yet — here’s the loop (and the [sample project](./examples/openai_support_agent/) runs offline without an API key):

```
  policy.yaml          mutiny run           .mutiny/tests/
  (invariants)  ──►  search → prove  ──►  minimized regressions
                         │                      │
                         ▼                      ▼
                   tool-call trace         mutiny test
                   (code oracle)           PASS / FAIL
```

Hosted lineage (optional): start API + UI with `./scripts/dev.sh`, then run without `--no-hosted`.

> Want to contribute a short terminal recording or screenshot? Open a PR — docs love it.

---

## Quick start

This repo is a **uv monorepo**. That is the supported install path today  
(**not** published to PyPI yet — `pip install mutiny` is on the roadmap).

### Prerequisites

- Python **≥ 3.11**
- [uv](https://docs.astral.sh/uv/)

### 1. Bootstrap the monorepo

```bash
git clone https://github.com/CodewithJha/mutiny.git
cd mutiny
uv sync --extra dev
```

This installs Mutiny Core, the OpenAI Agents SDK adapter, and the `mutiny` CLI into the workspace.

### 2. Sample project (recommended first run)

```bash
cd examples/openai_support_agent
uv run mutiny init    # scaffolds .mutiny/adapter.py, policy.yaml, mutiny.yaml
uv run mutiny run --no-hosted
uv run mutiny test    # replay saved regressions after a finding is saved
```

The sample agent uses a scripted offline model when `OPENAI_API_KEY` is unset — good for local smoke and CI.

### 3. Your own OpenAI Agents SDK project

```bash
cd /path/to/your-agent
uv run --directory /path/to/mutiny mutiny init --path .
# edit .mutiny/adapter.py  → AGENT_REF + POLICY_CONTEXT
# edit policy.yaml         → your tool names and rules
uv run --directory /path/to/mutiny mutiny run --path . --no-hosted
uv run --directory /path/to/mutiny mutiny test --path .
```

`mutiny init` writes:

| File | Role |
|---|---|
| `.mutiny/adapter.py` | Wires Adapter #1 to your agent export |
| `policy.yaml` | Deterministic tool-use invariants |
| `mutiny.yaml` | Campaign defaults |

### 4. Optional: Hosted UI

```bash
# from repo root
./scripts/dev.sh
# API :8000 · UI http://127.0.0.1:3000
```

Then `mutiny run` (without `--no-hosted`) prefers the Hosted API when reachable.

**Docs:** [`docs/`](./docs/) — start at [`docs/README.md`](./docs/README.md).

---

## How it works

```
1. Connect your agent     → adapter (MVP: OpenAI Agents SDK)
2. Declare invariants     → policy.yaml (deterministic tool rules)
3. Search                 → evolutionary campaign mutates attack conversations
4. Prove                  → code evaluates tool calls on the trace (not an LLM judge)
5. Minimize               → smallest reproduction that still violates
6. Freeze                 → permanent regression under .mutiny/tests/
```

```
Your agent project
        ↑
OpenAI Agents SDK Adapter   ← Adapter #1 (shipped)
        ↑
   Adapter Layer            ← future adapters (contributions welcome)
        ↑
   Mutiny Core              ← framework-independent engine
        ↑
   CLI (init / run / test)  ← primary
   Hosted API + UI          ← secondary (lineage / ops)
```

---

## Architecture

Short version: **one Core, thin adapters, CLI-first.**

| Layer | Location | Role |
|---|---|---|
| **Core** | `packages/mutiny_core/` | Policy oracle, campaign, fitness, minimize, regression |
| **Adapter #1** | `packages/mutiny_openai_agents/` | OpenAI Agents SDK → your local agent |
| **CLI** | `packages/mutiny_cli/` | `mutiny init` / `run` / `test` |
| **Sample** | `examples/openai_support_agent/` | Customer-style reference target |
| **Hosted** | `apps/api/`, `apps/web/` | Optional lineage / ops |

Core must not import framework SDKs. New frameworks = new adapters on the same `TargetAdapter` port — Core stays put.

Deep dive: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/SYSTEM_DESIGN.md`](./docs/SYSTEM_DESIGN.md).

---

## Adapters

| Adapter | Status |
|---|---|
| **OpenAI Agents SDK** | Shipped (Adapter #1) |
| LangGraph | Wanted — [roadmap](./docs/ROADMAP.md) / good first epic |
| CrewAI | Wanted |
| PydanticAI | Wanted |
| AutoGen | Wanted (later) |
| Localhost OpenAI-compatible HTTP | Wanted |

Building an adapter? Start from `packages/mutiny_core`’s `TargetAdapter` port and open an issue so we can align on the interface. See [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Commands

| Command | What it does |
|---|---|
| `mutiny init` | Scaffold adapter stub + `policy.yaml` + `mutiny.yaml` |
| `mutiny run` | Load adapter + policy; run a campaign; minimize / save regressions |
| `mutiny test` | Replay regressions under `.mutiny/tests/` (PASS / FAIL / SKIPPED) |

---

## Contributing

PRs welcome — especially adapters, policy packs, tests, and docs clarity.

```bash
uv sync --extra dev
uv run pytest tests/unit -q
```

- **Guide:** [CONTRIBUTING.md](./CONTRIBUTING.md)
- **Conduct:** [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)
- **Good first ideas:** new `TargetAdapter`s, example policies, minimize/regression coverage, clearer init errors
- **Issues:** [github.com/CodewithJha/mutiny/issues](https://github.com/CodewithJha/mutiny/issues)

If this engine is useful, a star helps other agent builders find it. Forks and issues are welcome too.

---

## Roadmap

| Phase | Focus |
|---|---|
| **Now** | Engine-first MVP · Adapter #1 (OpenAI Agents SDK) · CLI · minimize / regress · optional Hosted |
| **Next** | OSS hygiene · clearer package story · demos / screenshots · good-first-issue labeling |
| **Beta** | LangGraph / CrewAI / PydanticAI / HTTP adapters · policy packs · exportable reports |
| **v1** | Stable contracts · CI GitHub Action for regression replay · authenticated Hosted |

Full detail: [`docs/ROADMAP.md`](./docs/ROADMAP.md).

**Wanted contributor areas:** framework adapters, policy operator coverage, Hosted UX polish, CI/DX.

---

## Safety

Authorized testing only. MVP targets are local projects / in-process or localhost with sandboxed mock tools. Mutiny is **not** an open-internet attack proxy.

---

## License

[MIT](./LICENSE) © 2026 Priyanshu Jha / CodewithJha

---

### Status (honest)

Hackathon-era MVP in active development. Product thesis is engine-first + customer project via adapter. Hosted also exercises a bundled demo agent as an interim harness — useful for demos, **not** the primary user story. PyPI publish is planned; monorepo `uv` is the path that works today.
