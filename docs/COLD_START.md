# Mutiny — Cold start checklist

| Field | Value |
|---|---|
| **Status** | Pivot-aware bootstrap (CLI path planned; harness available) |
| **Last updated** | 2026-08-07 |
| **Pin** | [`config/demo_pin.json`](../config/demo_pin.json) |

Use this on a clean machine. Competitive claims stay frozen to [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md).

**Product path (intended):** Mutiny is a behavioral fuzz-testing engine — install into your agent project (Hackathon MVP: OpenAI Agents SDK via Adapter #1). See root [README](../README.md) and [DEMO_SCRIPT](./DEMO_SCRIPT.md). Until M2–M3 land, use the **interim harness** below for reliability and Hosted demos; label it as a sample/reference agent.

---

## 1. Prerequisites

- [ ] Python ≥ 3.11, [`uv`](https://github.com/astral-sh/uv), Node.js ≥ 20, `npm`
- [ ] Repo cloned; no secrets committed (copy `.env.example` → `.env` only if using Featherless LLM)
- [ ] Ports `8000` and `3000` free on localhost (Hosted)

LLM key is **optional**. Demo pin defaults to template mutation fallback (deterministic offline gate).

---

## 2. Install (monorepo)

```bash
uv sync --extra dev
cd apps/web && npm install && cd ../..
```

**Intended customer install (when packaged):**

```bash
pip install mutiny
cd your-agent-project   # MVP: OpenAI Agents SDK
mutiny init
# edit .mutiny/adapter.py
mutiny run
```

---

## 3. Reliability gate (required for harness demos)

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

**One command:**

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

**Or two terminals** (see root [README](../README.md)).

Verify:

- [ ] `GET http://127.0.0.1:8000/api/health` → `status: ok`, `api`/`db` true  
- [ ] Open `http://127.0.0.1:3000` — safety banner visible; attestation checkbox  
- [ ] `/policies` and `/tests` load  
- [ ] Narrative: sample/reference agent, not “this is the product”  

---

## 5. Demo day (T−30)

Follow [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) §0. Prefer clone sample → init → run; fall back to Hosted harness if CLI path is WIP.

Pinned seeds (harness): **5, 7, 11** in `config/demo_pin.json`.

Nuclear options: guided/template pin, smaller N/G, or [backup fixture path](../examples/demo/README.md).

---

## 6. Optional docker-compose

```bash
docker compose up --build
```

See root `docker-compose.yml` (API + web). Prefer `scripts/dev.sh` for laptop demos.
