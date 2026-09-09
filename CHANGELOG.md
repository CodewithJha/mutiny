# Changelog

All notable changes to Mutiny are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).  
Published on PyPI as **`mutiny-ai`** (+ [`mutiny-core`](https://pypi.org/project/mutiny-core/), [`mutiny-openai-agents`](https://pypi.org/project/mutiny-openai-agents/)) — see [docs/PUBLISHING.md](./docs/PUBLISHING.md).

## [Unreleased]

### Security

- **M-PR1 Hosted kill-switch** — Hosted API refuses `openai_agents` + `project_path` customer adapter execution by default (`403 project_exec_disabled`). Trusted `in_process_demo` harness unchanged. Opt-in: `MUTINY_ALLOW_PROJECT_EXEC=1` (single-operator localhost only; not a sandbox). Local CLI adapter loading unchanged.
- **M-PR2 Local CLI default** — `mutiny run` executes locally by default. Hosted requires explicit `--hosted` and/or `--hosted-url`. Config `hosted.api_url` alone never selects Hosted. Explicit Hosted failures do not silently fall back to local.
- **M-PR3 Secret redaction** — Deterministic `[REDACTED]` sanitization of common credential fields and `Authorization: Bearer` strings on persist/display paths (traces, hits, SSE/event payloads, test evidence). Runtime policy evaluation still sees raw in-memory traces. Not a general secret scanner.
- **M-PR4 DB path hygiene** — Hosted API honors `MUTINY_DB_PATH` for the real SQLite file (precedence: explicit `create_app` path → env → `data/mutiny.sqlite`). Invalid/empty paths fail closed with no silent fallback. Parent directories are created when missing. Backup/restore tooling is still out of scope.
- **M-PR5 CI completeness** — PR CI gates unit + offline integration + reliability (Python 3.11/3.12), local CLI sample smoke, web typecheck/build, and publishable package builds. Publish verify reads versions from each package `pyproject.toml` (no hardcoded `0.1.0`).
- **M-PR6 Policy-general seeds/mutators** — Core/CLI/API defaults use `default_policy_seeds` from `AttackFocus` (ADR-020). Template/LLM mutators probe focus tools/args/thresholds instead of hardcoded refund/`ord_1001`/`amount>200`. `boundary_refund_seeds` remains a demo/harness helper.

### Planned

- Additional framework adapters (LangGraph, CrewAI, PydanticAI, …)
- Dedicated GitHub Action for customer-project `mutiny test` replay packaging (sample path covered by CLI smoke + suites)
## [0.1.0] — 2026-08-09

Initial public repository promotion.

### Added

- **Mutiny Core** — policy oracle, evolutionary campaign, minimize, regression replay (`packages/mutiny_core/`)
- **Adapter #1** — OpenAI Agents SDK (`packages/mutiny_openai_agents/`)
- **CLI** — `mutiny init` / `run` / `test` (`packages/mutiny_cli/`) — PyPI: [`mutiny-ai`](https://pypi.org/project/mutiny-ai/)
- **Sample project** — `examples/openai_support_agent/` (offline scripted model without API key)
- **Optional Hosted** — API (`apps/api/`) + UI (`apps/web/`) for campaign lineage
- Docs hub under `docs/`, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT
- CI workflow (unit tests) and good-first-issue catalog
- GitHub Actions workflow + `scripts/publish_pypi.sh` for ordered PyPI upload

### Notes

- Install with `pip install mutiny-ai` (CLI command `mutiny`). Contributors: `uv sync --extra dev` (root `pip install -e .` is unsupported).
- Hosted UI is secondary; CLI local default (`mutiny run`) is the primary path; Hosted is `--hosted` opt-in.
- Bundled sample / demo agents are **reference harnesses**, not the product.

[Unreleased]: https://github.com/CodewithJha/mutiny/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CodewithJha/mutiny/releases/tag/v0.1.0
