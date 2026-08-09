# Publishing Mutiny packages to PyPI

End users install **`mutiny-ai`** (CLI command stays `mutiny`). That meta/CLI wheel depends on:

| PyPI name | Path | Role | Status |
|---|---|---|---|
| [`mutiny-core`](https://pypi.org/project/mutiny-core/) | `packages/mutiny_core` | Policy oracle / campaign kernel | **Published** (`0.1.0`) |
| [`mutiny-openai-agents`](https://pypi.org/project/mutiny-openai-agents/) | `packages/mutiny_openai_agents` | Adapter #1 | **Published** (`0.1.0`) |
| [`mutiny-ai`](https://pypi.org/project/mutiny-ai/) | `packages/mutiny_cli` | Console script `mutiny` | **Published** (`0.1.0`) — preferred short name |

> **Why not `pip install mutiny`?** The name [`mutiny`](https://pypi.org/project/mutiny/) is already taken (unrelated Revolt API wrapper). [`mutiny-sdk`](https://pypi.org/project/mutiny-sdk/) is also taken. We publish as **`mutiny-ai`**.

Do **not** publish the repo-root `name = "mutiny"` workspace project — it is not a user wheel.

End users: `pip install mutiny-ai` then `mutiny init`.

---

## Credentials for subsequent releases

Use one of the two paths below for version bumps after `0.1.0`.

### Option A — API token (fastest local publish)

1. Create / sign in: https://pypi.org/account/register/ (enable 2FA)
2. Create token: https://pypi.org/manage/account/token/
   - **Scope:** Entire account (needed for first upload of new project names)
   - Copy the value (starts with `pypi-`)
3. Publish:

```bash
cd /path/to/mutiny
export UV_PUBLISH_TOKEN='pypi-...'   # paste your token
chmod +x scripts/publish_pypi.sh
./scripts/publish_pypi.sh
```

Equivalent manual commands:

```bash
export UV_PUBLISH_TOKEN='pypi-...'

uv build --out-dir dist/core packages/mutiny_core
uv publish --token "$UV_PUBLISH_TOKEN" dist/core/*

uv build --out-dir dist/openai packages/mutiny_openai_agents
uv publish --token "$UV_PUBLISH_TOKEN" dist/openai/*

uv build --out-dir dist/cli packages/mutiny_cli
uv publish --token "$UV_PUBLISH_TOKEN" dist/cli/*
```

### Option B — Trusted Publishing (GitHub Actions, no long-lived token)

1. PyPI → [Publishing](https://pypi.org/manage/account/publishing/) → add a **pending** publisher **three times** (one per project name):

| Field | Value |
|---|---|
| PyPI project name | `mutiny-core`, then `mutiny-openai-agents`, then `mutiny-ai` |
| Owner | `CodewithJha` |
| Repository | `mutiny` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

2. GitHub repo → Settings → Environments → create **`pypi`** (optional protection rules).
3. Push `.github/workflows/publish.yml` (already in repo) → Actions → **Publish to PyPI** → Run workflow  
   (or publish a GitHub Release).

Optional fallback secret: repo secret `UV_PUBLISH_TOKEN` (used if set; otherwise OIDC Trusted Publishing).

**Do not** set `UV_PUBLISH_TOKEN` to an empty value in CI — `uv` then rejects Trusted Publishing with *“a username and a password are not allowed when using trusted publishing”*. Leave the secret unset, or set a real `pypi-…` token.

The Actions workflow skips any version that is already on PyPI (idempotent re-runs / manual-first uploads).

---

## Publish order (required)

Always: **mutiny-core** → **mutiny-openai-agents** → **mutiny-ai**.

Bump `version` in each package’s `pyproject.toml` together for a release (keep versions aligned).

---

## Verify (after upload)

```bash
python3 -m venv /tmp/mutiny-check && source /tmp/mutiny-check/bin/activate
pip install -U pip
pip install mutiny-ai
mutiny --help
pip index versions mutiny-ai
```

User-facing docs already lead with `pip install mutiny-ai` (keep git install as an optional footnote).

---

## Optional: install from git

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
```
