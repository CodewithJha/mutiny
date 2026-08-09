# Contributing to Mutiny

Thanks for helping make AI agent testing more honest. Mutiny is a **behavioral
fuzz-testing engine**: Core stays framework-independent; adapters connect real
agent projects.

**New here?** Aim for a **fork → PR in about 30 minutes** on a docs/test/CLI
nit. Larger adapters need an issue first.

## 30-minute path (fork → PR)

1. **Fork** [CodewithJha/mutiny](https://github.com/CodewithJha/mutiny) and clone your fork.
2. **Sync** the workspace (contributors use source; users install `mutiny-ai`):

   ```bash
   uv sync --extra dev
   uv run mutiny --help
   uv run pytest tests/unit -q
   ```

3. **Optional smoke** (sample project, offline — no API key):

   ```bash
   cd examples/openai_support_agent
   uv run mutiny init
   uv run mutiny run --no-hosted
   # mutiny test after a finding is saved under .mutiny/tests/
   cd ../..
   ```

4. **Pick a small task** from [docs/GOOD_FIRST_ISSUES.md](./docs/GOOD_FIRST_ISSUES.md)
   or an open issue labeled [`good first issue`](https://github.com/CodewithJha/mutiny/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
5. **Branch**, make a focused change, re-run `uv run pytest tests/unit -q`.
6. **Open a PR** using the template. Link the issue. One concern per PR.

Optional Hosted: `./scripts/dev.sh` (if `apps/web/node_modules` is missing, `cd apps/web && npm install` first) then `curl -sf http://127.0.0.1:8000/api/health`.

## Install

Full detail: [README → Install](./README.md#install).

**Prerequisites:** Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), git. Node.js ≥ 20 + npm only if you run the Hosted UI.

```bash
git clone https://github.com/CodewithJha/mutiny.git
cd mutiny
uv sync --extra dev
uv run mutiny --help
```

Alternate (per-package editable pip — install siblings together):

```bash
pip install -e packages/mutiny_core -e packages/mutiny_openai_agents -e packages/mutiny_cli
```

User-facing PyPI name for the CLI package is **`mutiny-ai`** (see [docs/PUBLISHING.md](./docs/PUBLISHING.md)).

## Project layout (where to change things)

| Area | Path | Notes |
|---|---|---|
| Core engine | `packages/mutiny_core/` | Policy oracle, campaign, minimize, regression — **no framework SDKs** |
| Adapter #1 | `packages/mutiny_openai_agents/` | OpenAI Agents SDK |
| CLI | `packages/mutiny_cli/` | `mutiny init` / `run` / `test` |
| Sample project | `examples/openai_support_agent/` | Customer-style target for docs + offline CI |
| Hosted API / UI | `apps/api/`, `apps/web/` | Secondary lineage surface |
| Tests | `tests/unit`, `tests/integration`, `tests/reliability` | Prefer unit tests for Core changes |
| Docs hub | `docs/` | Start at [`docs/README.md`](./docs/README.md) |

## Good First Issues / Help Wanted

| Label | Meaning |
|---|---|
| `good first issue` | Small, well-scoped; docs/tests/CLI/a11y/examples preferred. Safe for a first PR. |
| `help wanted` | Maintainers want help; may need a short design note (e.g. new adapter stub). |
| `docs` / `frontend` / `backend` / `cli` / `tests` / `a11y` / `examples` | Area filters — combine with the above. |

**Guidance for newcomers**

- Start from [docs/GOOD_FIRST_ISSUES.md](./docs/GOOD_FIRST_ISSUES.md) (≥30 catalogued ideas).
- Comment on the GitHub issue before large work so nobody duplicates effort.
- Do **not** redesign Core, campaign search, policy language, or Hosted product flows in a first PR.
- First PRs that shine: cheatsheets, CLI help text, unit tests, sample policy comments, a11y labels, refreshed Hosted screenshots.

**Guidance for maintainers**

- When filing easy work, add `good first issue` + an area label and a concrete acceptance check.
- Use `help wanted` for adapter scaffolds and CI that need interface agreement.
- Keep the catalog and open issues in sync when items ship.

## Ideas that fit the architecture

- **New adapters** on the existing `TargetAdapter` port (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP) — see [docs/ROADMAP.md](./docs/ROADMAP.md); brainstorm in Discussions, then open an issue before a large PR.
- Policy examples / packs for common tool-use invariants.
- Docs clarity: sample project path vs customer project path.
- Test coverage for policy operators, minimize, and regression replay.
- CI / DX: better failure messages from `mutiny init` / `mutiny test`.

## Where to ask

| Need | Where |
|---|---|
| Brainstorm / feature ideas | [Discussions → Ideas](https://github.com/CodewithJha/mutiny/discussions/categories/ideas) (start from [Feature Requests & Community Ideas](https://github.com/CodewithJha/mutiny/discussions/12)) |
| Actionable bug or scoped task | [GitHub Issues](https://github.com/CodewithJha/mutiny/issues) |
| “How do I…?” | [Discussions → Q&A](https://github.com/CodewithJha/mutiny/discussions/categories/q-a) |
| Security | [SECURITY.md](./SECURITY.md) — private only |

**Discussions = explore. Issues = actionable work** with a clear goal. Large adapters: discuss first, then open an issue before a big PR.

## How to run tests

```bash
uv sync --extra dev
uv run pytest tests/unit -q          # default for most PRs
uv run pytest tests/integration -q   # when touching API / Hosted / sample loop
uv run pytest tests/reliability -q   # when touching campaign / minimize / flaky paths
```

Optional offline smoke: `cd examples/openai_support_agent && uv run mutiny init && uv run mutiny run --no-hosted`.

## Pull request etiquette

1. **One concern per PR** when possible (adapter vs Core vs docs).
2. Keep Core free of framework imports — adapters own SDK glue.
3. Add or update tests for behavioral changes; run `uv run pytest tests/unit -q`.
4. Don’t claim PyPI install or adapters that aren’t shipped yet.
5. Authorized testing only — no open-internet attack proxy behavior.
6. Be kind in review; assume good intent. See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## How reviews work

- Maintainers review for scope, Core/adapter boundaries, and honest docs claims.
- Expect at least one pass of feedback on non-trivial PRs; small docs/test PRs often merge faster.
- Link the related issue (`Fixes #N`). If feedback asks for a design change on Core/campaign/policy, pause and discuss — don’t redesign in the same PR.
- Volunteer maintainers: best effort. Ping politely if a PR sits idle for a week+.
- Disagreement is fine; keep it specific and kind ([CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)).

## Commit style

Short, imperative messages that say *why* when it isn’t obvious:

- `fix: refuse regression save when not reproducible`
- `docs: clarify customer-project quick start`
- `feat(adapter): scaffold LangGraph TargetAdapter stub`

## Getting help

- Stuck on a `good first issue`? Ask in the issue comments — we’re happy to help.
- Broader questions: [Discussions](https://github.com/CodewithJha/mutiny/discussions) or [SUPPORT.md](./SUPPORT.md)
- Architecture: [`docs/`](./docs/) — [ARCHITECTURE.md](./docs/ARCHITECTURE.md), [ROADMAP.md](./docs/ROADMAP.md) / [Roadmap issue](https://github.com/CodewithJha/mutiny/issues/11)
