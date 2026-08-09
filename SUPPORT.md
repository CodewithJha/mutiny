# Support

## How to get help

| Need | Where |
|---|---|
| Bug report | [GitHub Issues](https://github.com/CodewithJha/mutiny/issues/new?template=bug_report.yml) |
| Brainstorm / feature ideas | [Discussions → Ideas](https://github.com/CodewithJha/mutiny/discussions/categories/ideas) ([community thread](https://github.com/CodewithJha/mutiny/discussions/12)) |
| Actionable enhancement (scoped) | [GitHub Issues](https://github.com/CodewithJha/mutiny/issues/new?template=feature_request.yml) |
| “How do I…?” / design chat | [GitHub Discussions](https://github.com/CodewithJha/mutiny/discussions) |
| Security vulnerability | [SECURITY.md](./SECURITY.md) — private disclosure only |
| Contributing workflow | [CONTRIBUTING.md](./CONTRIBUTING.md) |
| Architecture / product intent | [`docs/`](./docs/README.md) · [Roadmap issue](https://github.com/CodewithJha/mutiny/issues/11) |

## Before you open an issue

1. Confirm install path: **from source** with `uv sync --extra dev` (not on PyPI yet).
2. Try the sample project: `examples/openai_support_agent/` with `uv run mutiny …`.
3. For Hosted: `curl -sf http://127.0.0.1:8000/api/health` and see [Troubleshooting](./README.md#troubleshooting).
4. Search existing issues for duplicates.

## What maintainers can reasonably help with

- Reproducing Core / CLI / Adapter #1 failures on supported Python (≥ 3.11)
- Clarifying policy operators, campaign flags, and regression replay
- Reviewing adapter PRs that respect the `TargetAdapter` port
- Doc fixes and good-first-issue guidance

## What we can’t promise

- Private Slack / Discord support for every fork
- Debugging production agent frameworks outside Adapter #1 without a minimal repro
- Guaranteeing timelines for new framework adapters (LangGraph, CrewAI, …) — those are contribution-friendly roadmap items

## Response expectations

Volunteer maintainers. Best effort on issues with a clear repro and environment details. Security reports follow [SECURITY.md](./SECURITY.md).
