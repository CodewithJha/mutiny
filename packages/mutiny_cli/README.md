# mutiny-ai

**PyPI package:** `mutiny-ai`  
**CLI command:** `mutiny`

Install into *your* agent project (not by cloning this monorepo):

```bash
pip install mutiny-ai
mutiny init
mutiny run
mutiny test
```

> `mutiny` on PyPI is an unrelated project. The Mutiny fuzz engine publishes as **`mutiny-ai`**; the console script remains `mutiny`.

This package pulls in **mutiny-core** and the **mutiny-openai-agents** adapter so one install covers init / run / test for OpenAI Agents SDK projects.

## Source / editable (contributors)

From the monorepo root:

```bash
pip install -e packages/mutiny_core -e packages/mutiny_openai_agents -e packages/mutiny_cli
# or: uv sync --extra dev
```

See the [repository README](https://github.com/CodewithJha/mutiny#install) and [PUBLISHING.md](../../docs/PUBLISHING.md).
