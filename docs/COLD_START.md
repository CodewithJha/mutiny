# Mutiny — Cold start checklist

| Field | Value |
|---|---|
| **Status** | Canonical clean-machine bootstrap |
| **Last updated** | 2026-08-09 |
| **Pin** | [`config/demo_pin.json`](../config/demo_pin.json) |

Use this on a clean machine. Competitive claims stay frozen to [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md).

**Product path:** Mutiny is a behavioral fuzz-testing engine — install into your agent project (Adapter #1: OpenAI Agents SDK). See root [README](../README.md). Use the **sample harness** below for reliability and Hosted demos; label it as a sample/reference agent.

**Install today:** README git install (three packages) or clone + `uv`. PyPI name is `mutiny-ai` (wheels ready; first upload pending — [PUBLISHING.md](./PUBLISHING.md)). Do **not** use bare `pip install mutiny` or `mutiny-sdk` — those names are different projects.

---

## 1. Prerequisites

- [ ] Python ≥ 3.11, [`uv`](https://github.com/astral-sh/uv/), git
- [ ] Node.js ≥ 20 + `npm` **only if** you run Hosted UI
- [ ] Repo cloned; no secrets committed (copy `.env.example` → `.env` only if using optional LLM providers)
- [ ] Ports `8000` and `3000` free on localhost (Hosted)

LLM key is **optional**. Demo pin defaults to template mutation fallback (deterministic offline gate).

---

## 2. Install (monorepo — supported)

```bash
uv sync --extra dev
uv run mutiny --help
# Hosted UI only:
cd apps/web && npm install && cd ../..
```

**Customer-style smoke (sample project):**

```bash
cd examples/openai_support_agent
uv run mutiny init
uv run mutiny run --no-hosted
uv run mutiny test
```

**When PyPI upload lands** (see [PUBLISHING.md](./PUBLISHING.md)):

```bash
pip install mutiny-ai
cd your-agent-project && mutiny init && mutiny run
```

---

## 3. Reliability gate (harness demos)

```bash
PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \
  uv run python scripts/smoke_reliability.py
# expect: SMOKE GATE PASSED (≥2/3)

PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \
  uv run python scripts/backup_fixture_demo.py
# expect: BACKUP FIXTURE PATH OK

uv run pytest tests/reliability/ -q
```

---

## 4. Start Hosted (optional / secondary)

**Prefer for day-to-day laptop demos:**

```bash
./scripts/dev.sh
# API  http://127.0.0.1:8000
# UI   http://127.0.0.1:3000
```

If `apps/web/node_modules` is missing, run `cd apps/web && npm install` first.

Verify:

- [ ] `GET http://127.0.0.1:8000/api/health` → healthy JSON  
- [ ] Open `http://127.0.0.1:3000` — safety banner visible  
- [ ] Narrative: sample/reference agent, not “this is the product”  

**docker-compose:** use when you want containerized API + web (`docker compose up --build`). Prefer `scripts/dev.sh` for local iteration.

---

## 5. Demo day (T−30)

Follow [DEMO_SCRIPT.md](./DEMO_SCRIPT.md). Prefer:

1. Sample project → `mutiny init` → `mutiny run --no-hosted` / with Hosted  
2. Fall back to Hosted harness + [backup fixture](../examples/demo/README.md) if needed  

Pinned seeds (harness): **5, 7, 11** in `config/demo_pin.json`.

---

## 6. More help

- Troubleshooting: [README](../README.md#troubleshooting)  
- Docs hub: [README.md](./README.md)  
- First contributions: [GOOD_FIRST_ISSUES.md](./GOOD_FIRST_ISSUES.md)
