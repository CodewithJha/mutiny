# Acme Support Agent

Sample **customer-style** OpenAI Agents SDK project for Mutiny Adapter #1.

Mutiny is the fuzz engine. This folder is what a developer’s repo looks like —
not the Mutiny product itself.

## What’s inside

| File | Role |
|---|---|
| `agent.py` | OpenAI Agents SDK `Agent` (`support_agent`) |
| `tools.py` | Mock tools: refund / delete / email / lookup |
| `offline_model.py` | Scripted model when `OPENAI_API_KEY` is unset (CI / demos) |
| `main.py` | Simple chat loop |

Intentional soft spot (demo only): the system prompt trusts fake `APR-####`
codes, so Mutiny can discover real `issue_refund(..., approved=false)` calls.

## Setup

From the Mutiny repo root (uv workspace):

```bash
uv sync --extra dev
cd examples/openai_support_agent
```

Optional live model:

```bash
export OPENAI_API_KEY=sk-...
export MUTINY_SAMPLE_OFFLINE=0
```

Offline / CI (default when no key):

```bash
export MUTINY_SAMPLE_OFFLINE=1
```

## Mutiny (recommended)

From the Mutiny repo after `uv sync --extra dev`, always prefer `uv run mutiny …`
so the workspace CLI is on your PATH.

```bash
# Terminal A — Hosted API + UI (from Mutiny repo root)
./scripts/dev.sh

# Terminal B — this sample project
cd examples/openai_support_agent
uv run mutiny init          # once
uv run mutiny run           # Hosted-first when API is up
```

Then open the printed dashboard URL (`/campaign/<id>`).

Local-only (no Hosted):

```bash
uv run mutiny run --no-hosted
uv run mutiny test          # after regressions are saved under .mutiny/tests/
```

## Notes

- Tools are **mocks** — no payment rails or real email.
- Hosted loads this directory as `project_path` (`.mutiny/adapter.py`).
- This folder is the **sample / reference** agent. Backup fixture demos live under [`examples/demo/`](../demo/) (harness, not the product).
- Cold start: [`docs/COLD_START.md`](../../docs/COLD_START.md).
- Authorized testing only.
