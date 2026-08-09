# Mutiny

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/CodewithJha/mutiny/actions/workflows/ci.yml/badge.svg)](https://github.com/CodewithJha/mutiny/actions/workflows/ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)
[![GitHub issues](https://img.shields.io/github/issues/CodewithJha/mutiny)](https://github.com/CodewithJha/mutiny/issues)

**Behavioral fuzz-testing for AI agents.**  
_Define what your agent must never do. Then prove it can't._

| | |
|---|---|
| **What** | A fuzz engine you install into *your* agent project (`mutiny init` → `run` → `test`) |
| **Why** | Agents call tools that move money; prompts aren’t tests; chat evals miss tool-arg bugs |
| **Different** | Deterministic policy on **tool-call traces** (code proves) + minimize + permanent regressions — not LLM-as-judge, not “host our demo agent” |

Adapter #1 ships today: **OpenAI Agents SDK**. Same Core for every future adapter — contributions welcome.

```bash
pip install mutiny-ai
mutiny init
mutiny run
mutiny test
```

> Install package **`mutiny-ai`**; CLI command is **`mutiny`**. Do not use bare `pip install mutiny` or `mutiny-sdk` — those are unrelated projects.

---

## Table of contents

- [Why Mutiny](#why-mutiny)
- [Features](#features)
- [Screenshots & demo](#screenshots--demo)
- [Install](#install)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Adapters](#adapters)
- [Commands](#commands)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [FAQ](#faq)
- [Known limitations](#known-limitations)
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

## Screenshots & demo

Visual placeholders live under [`docs/assets/`](./docs/assets/) (intentional SVG mocks — swap for real PNG/GIF anytime; see that folder’s README).

### Loop storyboard

![Mutiny loop: init → run → violation → regression → test → PASS](./docs/assets/storyboard.svg)

```
  mutiny init  →  mutiny run  →  violation (code proves)
                                      │
                                      ▼
                               minimize + save
                               .mutiny/tests/
                                      │
                                      ▼
                               mutiny test  →  PASS (after fix)
```

**Real GIF later:** record the sample loop → save as `docs/assets/mutiny-demo.gif` → put the GIF above this storyboard in this section (keep the SVG as fallback). Details: [`docs/assets/README.md`](./docs/assets/README.md).

### Hosted & CLI frames

| View | Placeholder |
|---|---|
| Hero / landing | ![Hosted hero placeholder](./docs/assets/hero.svg) |
| Campaign / lineage | ![Campaign placeholder](./docs/assets/campaign.svg) |
| Policy | ![Policy placeholder](./docs/assets/policy.svg) |
| Tests | ![Tests placeholder](./docs/assets/tests.svg) |
| Regressions | ![Regressions placeholder](./docs/assets/regressions.svg) |
| CLI `mutiny run` | ![CLI run placeholder](./docs/assets/cli-run.svg) |

The [sample project](./examples/openai_support_agent/) runs offline without an API key. Hosted lineage (optional): `./scripts/dev.sh`, then `mutiny run` without `--no-hosted`.

> Real screenshots and terminal recordings are welcome PRs (`docs` / `examples` labels).

---

## Install

**For your agent project:**

```bash
pip install mutiny-ai
mutiny --help
```

Console script is **`mutiny`**. Do not use bare `pip install mutiny` or `mutiny-sdk` — those are unrelated projects.

<details>
<summary>Optional: install from git / source</summary>

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
```

</details>

### Prerequisites

| Tool | Required for | Notes |
|---|---|---|
| **Python ≥ 3.11** | Everything | Check with `python3 --version` |
| **pip** (or **[uv](https://docs.astral.sh/uv/)**) | Agent-project install | `pip install mutiny-ai` |
| **[uv](https://docs.astral.sh/uv/)** | Contributing / Hosted | Workspace sync + `uv run mutiny …` |
| **git** | Clone / optional git install | |
| **Node.js ≥ 20 + npm** | Optional Hosted UI | Only if you run `apps/web` / `./scripts/dev.sh` |

### Contributors: clone + uv workspace

```bash
git clone https://github.com/CodewithJha/mutiny.git
cd mutiny
uv sync --extra dev
uv run mutiny --help
```

### Contributors: editable `pip` (per package)

Root `pip install -e .` does **not** install the user CLI wheel (workspace root is not published). Install siblings together so deps resolve:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e packages/mutiny_core -e packages/mutiny_openai_agents -e packages/mutiny_cli

mutiny --help
```

### Optional Hosted (API + UI)

One command from the repo root:

```bash
./scripts/dev.sh
# API  http://127.0.0.1:8000
# UI   http://127.0.0.1:3000
# Health: GET http://127.0.0.1:8000/api/health
```

Or manually:

```bash
# terminal A — API
uv run uvicorn mutiny_api.main:app --host 127.0.0.1 --port 8000

# terminal B — UI (Node required)
cd apps/web && npm install && npm run dev
```

CLI campaigns without Hosted: pass `--no-hosted` to `mutiny run`.

---

## Quick start

### Sample project (recommended first run)

```bash
cd examples/openai_support_agent
uv run mutiny init    # scaffolds .mutiny/adapter.py, policy.yaml, mutiny.yaml
uv run mutiny run --no-hosted
uv run mutiny test    # replay saved regressions after a finding is saved
```

The sample agent uses a scripted offline model when `OPENAI_API_KEY` is unset — good for local smoke and CI. More detail: [`examples/openai_support_agent/`](./examples/openai_support_agent/).

### Your own OpenAI Agents SDK project

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

With Hosted running (`./scripts/dev.sh`), drop `--no-hosted` so `mutiny run` prefers the API when reachable.

**Docs:** [`docs/`](./docs/) — start at [`docs/README.md`](./docs/README.md).

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| `mutiny: command not found` | Run via `uv run mutiny …` from the repo after `uv sync --extra dev`, or activate the venv where you `pip install -e`’d the packages |
| `pip install -e .` at repo root fails | Expected — use `uv sync --extra dev` or the per-package editable installs above |
| Hosted UI won’t start | Install Node ≥ 20, then `cd apps/web && npm install` |
| Port already in use | Free **8000** (API) and **3000** (UI), or change the ports in `scripts/dev.sh` / Next |
| API looks down | `curl -sf http://127.0.0.1:8000/api/health` — expect JSON with a healthy status |
| Campaign can’t reach Hosted | Start `./scripts/dev.sh`, or use `mutiny run --no-hosted` for local-only |
| Sample agent needs a live model | Set `OPENAI_API_KEY`; leave unset (or `MUTINY_SAMPLE_OFFLINE=1`) for the offline scripted model |

Cold-start checklist: [`docs/COLD_START.md`](./docs/COLD_START.md).

---

## How it works

```
1. Connect your agent     → adapter (Adapter #1: OpenAI Agents SDK)
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
| `mutiny init [--path] [--force]` | Scaffold `.mutiny/adapter.py` + `policy.yaml` + `mutiny.yaml` |
| `mutiny run [--path] [--no-hosted] [--hosted-url]` | Load adapter + policy; campaign; minimize / save regressions |
| `mutiny test [--path] [--failed] [--json]` | Replay `.mutiny/tests/` (PASS / FAIL / SKIPPED) |

Full flag list: `uv run mutiny <cmd> --help`. Expanding this table from `--help` is a welcome docs PR.

---

## Roadmap

| Phase | Focus |
|---|---|
| **Current scope** | Engine-first Core · Adapter #1 (OpenAI Agents SDK) · CLI · minimize / regress · optional Hosted |
| **Next** | Real screenshots / GIF · contributor onboarding · more adapters |
| **Beta** | LangGraph / CrewAI / PydanticAI / HTTP adapters · policy packs · exportable reports |
| **v1** | Stable contracts · CI GitHub Action for regression replay · authenticated Hosted |

Full detail: [`docs/ROADMAP.md`](./docs/ROADMAP.md) · tracked as [🚀 Roadmap to v1.0](https://github.com/CodewithJha/mutiny/issues/11).

**Wanted contributor areas:** framework adapters, policy packs, tests, Hosted a11y/UX polish, CI/DX.

---

## Contributing

PRs welcome — especially adapters, policy packs, tests, docs, and a11y. Newcomers: start with a [`good first issue`](https://github.com/CodewithJha/mutiny/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) (fork → PR in about 30 minutes).

```bash
uv sync --extra dev
uv run pytest tests/unit -q
```

- **Guide (30-min path):** [CONTRIBUTING.md](./CONTRIBUTING.md)
- **Good first issues catalog:** [`docs/GOOD_FIRST_ISSUES.md`](./docs/GOOD_FIRST_ISSUES.md)
- **Ideas & brainstorming:** [Discussions](https://github.com/CodewithJha/mutiny/discussions/12)
- **Changelog / releases:** [CHANGELOG.md](./CHANGELOG.md)
- **Conduct / Security / Support:** [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) · [SECURITY.md](./SECURITY.md) · [SUPPORT.md](./SUPPORT.md)
- **Docs hub:** [`docs/README.md`](./docs/README.md)
- **Issues:** [github.com/CodewithJha/mutiny/issues](https://github.com/CodewithJha/mutiny/issues)

If this engine is useful, a star helps other agent builders find it. Fork the repo and open a PR — we’re glad to help in the comments.

---

## FAQ

**Is Mutiny on PyPI?**  
Yes — install with `pip install mutiny-ai` ([PyPI](https://pypi.org/project/mutiny-ai/)). CLI command is **`mutiny`**. Do not use bare `pip install mutiny` or `mutiny-sdk` — those are other projects.

**Which agent frameworks work today?**  
**Adapter #1: OpenAI Agents SDK** only. Others (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP) are roadmap / contribution targets on the same `TargetAdapter` port.

**Do I need an OpenAI API key?**  
No for the [sample project](./examples/openai_support_agent/) — it uses an offline scripted model when the key is unset. Your own live agent may need whatever keys that agent already uses.

**Is the Hosted UI required?**  
No. CLI is primary. Use `mutiny run --no-hosted` for local-only campaigns. Hosted adds lineage / ops when you want a browser.

**Is the bundled demo agent the product?**  
No. It’s a **reference harness** for docs and reliability. The product story is: install Mutiny into *your* agent project.

**Can I point Mutiny at random websites?**  
No. Authorized testing only — local / in-process / localhost. Not an open-internet attack proxy.

**Where do I ask for help?**  
[SUPPORT.md](./SUPPORT.md). Security → [SECURITY.md](./SECURITY.md).

---

## Known limitations

- **One shipped adapter** (OpenAI Agents SDK); multi-framework support is intentional future work, not missing polish of a single kernel.
- **Published on PyPI** as `mutiny-ai` (`pip install mutiny-ai`) — see [docs/PUBLISHING.md](./docs/PUBLISHING.md).
- **Policy expressiveness** is deliberately narrow (deterministic operators on tool calls) — not NL policies judged by an LLM.
- **Hosted** is optional and secondary; auth / multi-tenant cloud are not current scope.
- **Screenshots / recorded demo** — SVG placeholders ship in `docs/assets/`; real PNG/GIF contributions welcome.
- Sample and reference demo agents use **mock tools**; they are not production payment or email systems.
- See [CHANGELOG.md](./CHANGELOG.md) for Unreleased / initial release notes.

Honest scope detail: [`docs/ROADMAP.md`](./docs/ROADMAP.md) § Current scope.

---

## Safety

Authorized testing only. Current targets are local projects / in-process or localhost with sandboxed mock tools. Mutiny is **not** an open-internet attack proxy.

---

## License

[MIT](./LICENSE) © 2026 Priyanshu Jha / CodewithJha
