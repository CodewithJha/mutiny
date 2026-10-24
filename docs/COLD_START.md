# Mutiny — Cold start checklist

| Field | Value |
|---|---|
| **Status** | Canonical clean-machine bootstrap |
| **Last updated** | 2026-10-24 |
| **Pin** | [`config/demo_pin.json`](../config/demo_pin.json) |

Use this on a clean machine. Competitive claims stay frozen to [COMPETITOR_ANALYSIS.md](./COMPETITOR_ANALYSIS.md).

**Product path:** Mutiny is a behavioral fuzz-testing engine — install into your agent project (Adapter #1: OpenAI Agents SDK). See root [README](../README.md). Use the **sample harness** below for reliability and Hosted demos; label it as a sample/reference agent.

**Install:** `pip install mutiny-ai` (CLI: `mutiny`), or clone + `uv` for contributors. Do **not** use bare `pip install mutiny` or `mutiny-sdk` — those names are different projects. See [PUBLISHING.md](./PUBLISHING.md).

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
uv sync --group dev
uv run mutiny --help
# Hosted UI only:
cd apps/web && npm install && cd ../..
```

**Customer-style smoke (sample project):**

```bash
cd examples/openai_support_agent
uv run mutiny init
uv run mutiny run
uv run mutiny test
```

**Customer-style install (PyPI):**

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

### Containerized local demo (MUT-012 / #63)

Set `MUTINY_API_TOKEN` in your shell or an uncommitted `.env` file, then run:

```bash
docker compose up --build -d
curl -f http://127.0.0.1:8000/api/health
# Open http://127.0.0.1:3000
docker compose down
```

Both host ports publish only on `127.0.0.1`. The UI acts for its visitors using
the operator token, so keep it local or behind your own authenticated proxy.
Compose passes the same token to both services. The API's internal `0.0.0.0`
bind still fails closed without a token; the supported entrypoint remains
`python -m mutiny_api`.

Dependencies are installed at image build (`uv sync --locked --no-dev
--no-editable --package mutiny-api`, `npm ci`, `npm run build`). Runtime uses
non-root users and the prebuilt Python environment / Next.js standalone server.
Rebuild after dependency or source changes; use `scripts/dev.sh` for hot reload.
The web image's API rewrite destination is a **build argument**,
`MUTINY_API_URL` (Compose: `http://api:8000`), because Next.js bakes rewrites into
its build. The token is runtime-only; never supply it as a build argument.

Only a named `mutiny-data` volume is mounted at `/app/data`; neither container
mounts the host checkout. The database is `/app/data/mutiny.sqlite`, not the
host's `./data/mutiny.sqlite`. `docker compose down` retains the volume;
`docker compose down -v` deletes it. To back it up using the documented SQLite
backup API, stage the backup inside the volume and copy it out:

```bash
docker compose exec api python -c "import sqlite3; source=sqlite3.connect('/app/data/mutiny.sqlite'); dest=sqlite3.connect('/app/data/backup.sqlite'); source.backup(dest); dest.close(); source.close()"
docker compose cp api:/app/data/backup.sqlite ./mutiny-backup.sqlite
```

Keep backups private. Existing host `./data/` databases are not migrated
automatically; back them up and restore deliberately before switching. An
existing volume or an optional data-only bind mount must be writable by API
UID/GID `10001:10001`; fresh named volumes inherit image directory ownership.

### Railway API image

`railway.toml` selects the root Dockerfile's final `api` stage. Build dependencies
are already installed; startup runs the existing sample-ensure check and then
`python -m mutiny_api`, expanding Railway's `PORT`. Set `MUTINY_API_TOKEN` in the
service environment. No `uv sync` or package manager runs at boot. The sample
files are prepared during image build, preserving the existing ensure behavior
(MUT-066 is separate).

For persistence, attach a volume at `/app/data` with ownership allowing UID/GID
`10001:10001` to write it. Without a volume, database state is ephemeral across
replacement deployments. This change does not provide public UI authentication
or multi-tenant isolation; see [SECURITY.md](../SECURITY.md#container-deployment-mut-012--63).

---

## 5. Demo day (T−30)

Follow [DEMO_SCRIPT.md](./DEMO_SCRIPT.md). Prefer:

1. Sample project → `mutiny init` → `mutiny run` / `mutiny run --hosted`
2. Fall back to Hosted harness + [backup fixture](../examples/demo/README.md) if needed  

Pinned seeds (harness): **5, 7, 11** in `config/demo_pin.json`.

---

## 6. More help

- Troubleshooting: [README](../README.md#troubleshooting)  
- Docs hub: [README.md](./README.md)  
- First contributions: [GOOD_FIRST_ISSUES.md](./GOOD_FIRST_ISSUES.md)
