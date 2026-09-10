# Publishing Mutiny packages to PyPI

End users install **`mutiny-ai`** (CLI command stays `mutiny`). That meta/CLI wheel depends on:

| PyPI name | Path | Role | Status |
|---|---|---|---|
| [`mutiny-core`](https://pypi.org/project/mutiny-core/) | `packages/mutiny_core` | Policy oracle / campaign kernel | **0.2.0 RC** (git); PyPI may still show `0.1.0` until upload |
| [`mutiny-openai-agents`](https://pypi.org/project/mutiny-openai-agents/) | `packages/mutiny_openai_agents` | Adapter #1 | **0.2.0 RC** (git); PyPI may still show `0.1.0` until upload |
| [`mutiny-ai`](https://pypi.org/project/mutiny-ai/) | `packages/mutiny_cli` | Console script `mutiny` | **0.2.0 RC** (git); PyPI may still show `0.1.0` until upload |

> **Why not `pip install mutiny`?** The name [`mutiny`](https://pypi.org/project/mutiny/) is already taken (unrelated Revolt API wrapper). [`mutiny-sdk`](https://pypi.org/project/mutiny-sdk/) is also taken. We publish as **`mutiny-ai`**.

Do **not** publish the repo-root `name = "mutiny"` workspace project — it is not a user wheel.

End users: `pip install mutiny-ai` then `mutiny init` / `mutiny run` / `mutiny test` (Hosted not required).

---

## Release contract (required before upload)

Until **`0.2.0`** is uploaded, PyPI **`0.1.0` may lag the git tree**. Editable/`uv sync` success does **not** prove release integrity — checkout imports hide broken wheels.

Before every publish:

1. **Align versions** in all three `packages/*/pyproject.toml` (CI fails on mismatch). Runtime `__version__` comes from package metadata, not a hardcoded string. Sibling deps use `>=` the release minor (e.g. `mutiny-core>=0.2.0`) so pip cannot satisfy a new CLI wheel with stale `0.1.x` cores from the index.
2. **Build from the commit you intend to ship** (never an older checkout tagged with the same version).
3. **Verify artifacts offline** (sibling wheels together; no `PYTHONPATH`, no editable):

```bash
./scripts/verify_release_artifacts.sh
```

That script: builds wheels/sdists → installs into a fresh venv → asserts installed versions match `pyproject.toml` → `mutiny --help` / `mutiny db --help` / `mutiny init` → offline sample `mutiny run --no-hosted` (violation + minimize + regression save) → `mutiny test` FAIL then PASS after the documented sample fix → redaction smoke → Hosted operator `mutiny db backup` / `restore` when `mutiny-api` is installable from a freshly built workspace wheel.

4. **Install order for local wheels**: `mutiny-core` → `mutiny-openai-agents` → `mutiny-ai` (or pass all three paths to one `pip install` so pip cannot resolve `mutiny-*` from a stale PyPI index).
5. **Never re-upload the same version** expecting code changes — bump all three versions together, then publish. The publish workflow **fails** (does not silently skip) if the target version is already on PyPI.

PR CI job `package-build` runs the same artifact gate.

---

## Credentials for subsequent releases

Use one of the two paths below for version bumps after a published line (e.g. after `0.1.0` / `0.2.0`).

### Option A — API token (fastest local publish)

1. Create / sign in: https://pypi.org/account/register/ (enable 2FA)
2. Create token: https://pypi.org/manage/account/token/
   - **Scope:** Entire account (needed for first upload of new project names)
   - Copy the value (starts with `pypi-`)
3. Publish **only after** `./scripts/verify_release_artifacts.sh` passes:

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

The Actions workflow: aligns versions → runs `./scripts/verify_release_artifacts.sh` → uploads only versions **not** already on PyPI. If any package version is already published, the job **fails** (no silent skip) so a forgotten bump cannot report success while leaving stale `0.1.0` as the latest ship.

---

## Publish order (required)

Always: **mutiny-core** → **mutiny-openai-agents** → **mutiny-ai**.

Bump `version` in each package’s `pyproject.toml` together for a release (keep versions aligned).

---

## Verify (after upload)

```bash
python3 -m venv /tmp/mutiny-check && source /tmp/mutiny-check/bin/activate
pip install -U pip
pip install mutiny-ai==0.2.0
mutiny --help
python -c "from importlib.metadata import version; print(version('mutiny-ai'))"
pip index versions mutiny-ai
```

Prefer comparing `pip show mutiny-ai` / installed module contents against the commit you published — not against an unrelated local editable checkout.

User-facing docs already lead with `pip install mutiny-ai` (keep git install as an optional footnote).

---

## Optional: install from git

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
```
