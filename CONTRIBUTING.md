# Contributing to Mutiny

Thanks for helping make AI agent testing more honest. Mutiny is a **behavioral
fuzz-testing engine**: Core stays framework-independent; adapters connect real
agent projects.

## Install

Not on PyPI yet — clone and sync from source. Full detail: [README → Install](./README.md#install).

**Prerequisites:** Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), git. Node.js ≥ 20 + npm only if you run the Hosted UI.

```bash
git clone https://github.com/CodewithJha/mutiny.git
cd mutiny
uv sync --extra dev
uv run mutiny --help
```

Alternate (per-package editable pip — root `pip install -e .` does not work):

```bash
pip install -e packages/mutiny_core
pip install -e packages/mutiny_openai_agents
pip install -e packages/mutiny_cli
```

Optional Hosted: `./scripts/dev.sh` (API `:8000`, UI `:3000`). Health: `curl -sf http://127.0.0.1:8000/api/health`.

## Quick path

```bash
uv sync --extra dev
uv run pytest tests/unit -q
```

Optional reliability smoke (demo harness):

```bash
PYTHONPATH=apps/api/src:apps/demo_agent/src:packages/mutiny_core/src \
  uv run python scripts/smoke_reliability.py
```

## Project layout (where to change things)

| Area | Path | Notes |
|---|---|---|
| Core engine | `packages/mutiny_core/` | Policy oracle, campaign, minimize, regression — **no framework SDKs** |
| Adapter #1 | `packages/mutiny_openai_agents/` | OpenAI Agents SDK |
| CLI | `packages/mutiny_cli/` | `mutiny init` / `run` / `test` |
| Sample project | `examples/openai_support_agent/` | Customer-style target for docs + offline CI |
| Hosted API / UI | `apps/api/`, `apps/web/` | Secondary lineage surface |
| Tests | `tests/unit`, `tests/integration`, `tests/reliability` | Prefer unit tests for Core changes |

## Good first contributions

Ideas that fit the architecture without rewriting the kernel:

- **New adapters** on the existing `TargetAdapter` port (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP) — see [docs/ROADMAP.md](./docs/ROADMAP.md)
- Policy examples / packs for common tool-use invariants
- Docs clarity: sample project path vs customer project path
- Test coverage for policy operators, minimize, and regression replay
- CI / DX: better failure messages from `mutiny init` / `mutiny test`

Open an issue first for larger adapters so we can agree on the interface surface.

## Pull request etiquette

1. **One concern per PR** when possible (adapter vs Core vs docs).
2. Keep Core free of framework imports — adapters own SDK glue.
3. Add or update tests for behavioral changes; run `uv run pytest tests/unit -q`.
4. Don’t claim PyPI install or adapters that aren’t shipped yet.
5. Authorized testing only — no open-internet attack proxy behavior.
6. Be kind in review; assume good intent. See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## Commit style

Short, imperative messages that say *why* when it isn’t obvious:

- `fix: refuse regression save when not reproducible`
- `docs: clarify customer-project quick start`
- `feat(adapter): scaffold LangGraph TargetAdapter stub`

## Questions

Use [GitHub Issues](https://github.com/CodewithJha/mutiny/issues) or
[Discussions](https://github.com/CodewithJha/mutiny/discussions). Architecture
context lives in [`docs/`](./docs/) — start with
[ARCHITECTURE.md](./docs/ARCHITECTURE.md) and [ROADMAP.md](./docs/ROADMAP.md).
