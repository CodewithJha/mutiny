# mutiny-ai

**PyPI package:** [`mutiny-ai`](https://pypi.org/project/mutiny-ai/)  
**CLI command:** `mutiny`

Install into *your* agent project (not by cloning this monorepo).

```bash
pip install mutiny-ai
mutiny init
```

> Install package **`mutiny-ai`**. CLI command is **`mutiny`**. Do not use bare `pip install mutiny` or `mutiny-sdk` — those are unrelated projects.

This package depends on **mutiny-core** and **mutiny-openai-agents** (pulled in automatically from PyPI).

<details>
<summary>Optional: install from git / source</summary>

```bash
pip install \
  "mutiny-core @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_core" \
  "mutiny-openai-agents @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_openai_agents" \
  "mutiny-ai @ git+https://github.com/CodewithJha/mutiny.git#subdirectory=packages/mutiny_cli"
```

From the monorepo root (editable):

```bash
pip install -e packages/mutiny_core -e packages/mutiny_openai_agents -e packages/mutiny_cli
# or: uv sync --extra dev
```

</details>

See the [repository README](https://github.com/CodewithJha/mutiny#install) and [PUBLISHING.md](../../docs/PUBLISHING.md).
