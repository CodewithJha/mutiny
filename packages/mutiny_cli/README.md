# mutiny-ai

**PyPI package:** `mutiny-ai`  
**CLI command:** `mutiny`

Install into *your* agent project (not by cloning this monorepo). Until PyPI is live, install all three packages from git:

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
mutiny init
mutiny run
mutiny test
```

> PyPI name will be **`mutiny-ai`** (not yet published). CLI command is **`mutiny`**. Do not use bare `pip install mutiny` or `mutiny-sdk` — those are unrelated projects.

This package depends on **mutiny-core** and **mutiny-openai-agents**, so install siblings together until they are published.

## Source / editable (contributors)

From the monorepo root:

```bash
pip install -e packages/mutiny_core -e packages/mutiny_openai_agents -e packages/mutiny_cli
# or: uv sync --extra dev
```

See the [repository README](https://github.com/CodewithJha/mutiny#install) and [PUBLISHING.md](../../docs/PUBLISHING.md).
