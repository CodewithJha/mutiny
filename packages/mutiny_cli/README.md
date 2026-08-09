# mutiny-ai

**PyPI package:** `mutiny-ai`  
**CLI command:** `mutiny`

Install into *your* agent project (not by cloning this monorepo).

**After PyPI upload:**

```bash
pip install mutiny-ai
mutiny init
```

**Until then** (wheels are built; upload needs a PyPI token — see [PUBLISHING.md](../../docs/PUBLISHING.md)), install all three from git:

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
mutiny init
mutiny run
mutiny test
```

> PyPI name is **`mutiny-ai`**. CLI command is **`mutiny`**. Do not use bare `pip install mutiny` or `mutiny-sdk` — those are unrelated projects.

This package depends on **mutiny-core** and **mutiny-openai-agents**, so install siblings together until they are on PyPI.

## Source / editable (contributors)

From the monorepo root:

```bash
pip install -e packages/mutiny_core -e packages/mutiny_openai_agents -e packages/mutiny_cli
# or: uv sync --extra dev
```

See the [repository README](https://github.com/CodewithJha/mutiny#install) and [PUBLISHING.md](../../docs/PUBLISHING.md).
