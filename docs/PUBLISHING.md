# Publishing Mutiny packages to PyPI

End users install **`mutiny-ai`** (CLI command stays `mutiny`). That meta/CLI wheel depends on:

| PyPI name | Path | Role |
|---|---|---|
| `mutiny-core` | `packages/mutiny_core` | Policy oracle / campaign kernel |
| `mutiny-openai-agents` | `packages/mutiny_openai_agents` | Adapter #1 |
| `mutiny-ai` | `packages/mutiny_cli` | Console script `mutiny` |

> **Why not `pip install mutiny`?** The name [`mutiny`](https://pypi.org/project/mutiny/) is already taken (unrelated Revolt API wrapper). We publish as **`mutiny-ai`**.

Do **not** publish the repo-root `name = "mutiny"` workspace project — it is not a user wheel.

## Prerequisites

1. A PyPI account with 2FA: https://pypi.org/account/register/
2. An API token (Account settings → API tokens), scoped to the project(s) once created
3. Local tools: `uv` (recommended) or `pip` + `build` + `twine`

```bash
# one-time
pip install build twine
# or use: uv build / uv publish
```

Credentials (pick one):

- `~/.pypirc` with a `[pypi]` token, or
- env: `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=pypi-...`, or
- `UV_PUBLISH_TOKEN=pypi-...` for `uv publish`

## Publish order (required)

Publish dependencies first so installers can resolve them:

```bash
cd /path/to/mutiny

# 1) core
uv build packages/mutiny_core
uv publish packages/mutiny_core/dist/*

# 2) openai adapter
uv build packages/mutiny_openai_agents
uv publish packages/mutiny_openai_agents/dist/*

# 3) user-facing CLI (mutiny-ai)
uv build packages/mutiny_cli
uv publish packages/mutiny_cli/dist/*
```

Equivalent with build + twine:

```bash
python -m build packages/mutiny_core && twine upload packages/mutiny_core/dist/*
python -m build packages/mutiny_openai_agents && twine upload packages/mutiny_openai_agents/dist/*
python -m build packages/mutiny_cli && twine upload packages/mutiny_cli/dist/*
```

Bump `version` in each package’s `pyproject.toml` together for a release (keep them aligned at `0.1.0` for the first upload).

## Verify

```bash
pip install mutiny-ai
mutiny --help
```

## Before the first PyPI upload

From an agent project (no monorepo clone):

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
```

Install all three in one `pip install` so dependency names resolve from the same command (single subdirectory install of `mutiny_cli` alone cannot see local siblings until they exist on PyPI).
