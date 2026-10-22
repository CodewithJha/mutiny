# Acme Support Agent

Sample **customer-style** OpenAI Agents SDK project for Mutiny Adapter #1.

Mutiny is the fuzz engine. This folder is what a developer’s repo looks like —
not the Mutiny product itself.

## What’s inside

| File | Role |
|---|---|
| `agent.py` | OpenAI Agents SDK `Agent` (`support_agent`) |
| `tools.py` | Mock tools: refund / delete / email / lookup |
| `offline_model.py` | Scripted model when `OPENAI_API_KEY` is unset (CI / demos) |
| `main.py` | Simple chat loop |

Intentional soft spot (demo only): the system prompt trusts fake `APR-####`
codes, so Mutiny can discover real `issue_refund(..., approved=false)` calls.

## Setup

From the Mutiny repo root (uv workspace):

```bash
uv sync --group dev
cd examples/openai_support_agent
```

Optional live model:

```bash
export OPENAI_API_KEY=sk-...
export MUTINY_SAMPLE_OFFLINE=0
```

Offline / CI (default when no key):

```bash
export MUTINY_SAMPLE_OFFLINE=1
```

## Local FAIL to PASS walkthrough (recommended)

From the Mutiny repo after `uv sync --group dev`, always prefer `uv run mutiny …`
so the workspace CLI is on your PATH.

```bash
# From this sample directory; no Hosted process or API key required
uv run mutiny init
uv run mutiny run
uv run mutiny test
```

The campaign saves a verified violation under `.mutiny/tests/`. The first
`mutiny test` is expected to report **FAIL** for `refund_limit` and exit **1**:
the sample intentionally accepts fake approval codes. This confirms the
regression reproduces; it is not a replay error.

Apply the sample's existing policy enforcement switch in `.mutiny/adapter.py`:

```diff
-def create_adapter(*, enforce_refund_policy: bool = False) -> OpenAIAgentsAdapter:
+def create_adapter(*, enforce_refund_policy: bool = True) -> OpenAIAgentsAdapter:
```

Keep the saved regression and replay it:

```bash
uv run mutiny test
```

The refund regression now reports **PASS**, with exit **0**. The switch makes the
sample enforce refund limits instead of trusting approval strings. Production
agents need equivalent checks in their own trusted tool implementation. To
repeat the vulnerable demonstration, change the default back to `False`.
The release artifact gate uses this same switch in an isolated sample copy
([script](../../scripts/verify_release_artifacts.sh)).

## Optional Hosted lineage

Start `./scripts/dev.sh` from the repository root in another terminal, then run
`uv run mutiny run --hosted` from this sample and open the printed dashboard URL.
Execution stays local; Hosted receives redacted lineage through ingest. Hosted
does not load or execute this project's adapter.

## Notes

- Tools are **mocks** — no payment rails or real email.
- The [email recipient policy example](../policies/email_domain_confirmation.yaml)
  binds recipients to the customer address in trusted adapter context.
- Local CLI loads `.mutiny/adapter.py`; Hosted stores `project_path` as opaque metadata.
- This folder is the **sample / reference** agent. Backup fixture demos live under [`examples/demo/`](../demo/) (harness, not the product).
- Cold start: [`docs/COLD_START.md`](../../docs/COLD_START.md).
- Authorized testing only.
