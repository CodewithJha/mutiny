# Mutiny

**Mutiny is a behavioral fuzz-testing engine for AI agents.**

The Hackathon MVP ships with support for OpenAI Agents SDK projects through the first adapter. Future adapters (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP, …) are on the [roadmap](./docs/ROADMAP.md)—same Core, new adapters.

> Install Mutiny into your agent project → define what it must never do → discover policy breaks → prove them on tool-call traces → minimize → save permanent regression tests.

**Documentation:** [`docs/`](./docs/) — start at [`docs/README.md`](./docs/README.md).

## Install into your agent project

Primary workflow (intended product path):

```bash
# In your agent project (Hackathon MVP: OpenAI Agents SDK)
pip install mutiny

mutiny init
# → .mutiny/adapter.py   connect Mutiny to your agent
# → policy.yaml          tool-use invariants
# → mutiny.yaml          campaign defaults

# Edit .mutiny/adapter.py to load your agent, then:
mutiny run
# discovers tool calls → evolutionary campaign → verified violations
# → minimize → regression tests
```

| | |
|---|---|
| **Hackathon MVP** | ✓ OpenAI Agents SDK adapter (Adapter #1) |
| **Future** | Additional adapters on the same interface |

## Status

- **Product pivot (2026-08-07):** Mutiny is the engine; adapters connect frameworks. Primary path is *your* local agent via adapter + CLI (`mutiny init` / `mutiny run`). See [ADR-017](./docs/DECISION_LOG.md#adr-017--customer-owned-local-projects-primary-bundled-demo-secondary) and [ADR-018](./docs/DECISION_LOG.md#adr-018--adapter-first-architecture).
- **Codebase today:** Core loop + Hosted API/UI still exercise a **bundled demo agent** as an interim reference / testing harness. The OpenAI Agents SDK adapter + `mutiny init` CLI surfaces are the planned install path (docs describe intent; see [IMPLEMENTATION_PLAN](./docs/IMPLEMENTATION_PLAN.md)).
- Design canon: Inngest-inspired dark UI — [`DESIGN.md`](./DESIGN.md)
- Cold start: [`docs/COLD_START.md`](./docs/COLD_START.md) · Demo: [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)
- Devpost: [`docs/DEVPOST.md`](./docs/DEVPOST.md)
- Claims freeze: [`docs/COMPETITOR_ANALYSIS.md`](./docs/COMPETITOR_ANALYSIS.md)

## Develop (monorepo)

```bash
uv sync --extra dev
uv run pytest tests/ -q

# Reliability smoke against interim demo harness (≥2/3)
PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \
  uv run python scripts/smoke_reliability.py

# One-command Hosted (API :8000 + UI :3000) — optional visualization / ops surface
./scripts/dev.sh
# open http://127.0.0.1:3000
```

Or two terminals:

```bash
# Hosted API (terminal 1)
mkdir -p data
PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \
  uv run uvicorn mutiny_api.main:app --host 127.0.0.1 --port 8000

# Hosted UI (terminal 2) — proxies /api → :8000
cd apps/web && npm install && npm run dev
# open http://127.0.0.1:3000
```

Optional: `docker compose up --build`.

If `next dev --turbopack` 404s every route on macOS (`EMFILE: too many open files`), use the default `npm run dev` script (webpack + polling). Optional: `npm run dev:turbo`.

Pinned demo harness config: [`config/demo_pin.json`](./config/demo_pin.json).

## Safety

Authorized testing only. MVP targets are local projects / in-process or localhost with sandboxed mock tools. Mutiny is not an open-internet attack proxy.
