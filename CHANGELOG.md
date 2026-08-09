# Changelog

All notable changes to Mutiny are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).  
Published on PyPI as **`mutiny-ai`** (+ [`mutiny-core`](https://pypi.org/project/mutiny-core/), [`mutiny-openai-agents`](https://pypi.org/project/mutiny-openai-agents/)) — see [docs/PUBLISHING.md](./docs/PUBLISHING.md).

## [Unreleased]

### Planned

- Additional framework adapters (LangGraph, CrewAI, PydanticAI, …)
- CI GitHub Action for sample-project `mutiny test` replay (not shipped in 0.1.0)

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
- Hosted UI is secondary; CLI with `--no-hosted` is the primary local path.
- Bundled sample / demo agents are **reference harnesses**, not the product.

[Unreleased]: https://github.com/CodewithJha/mutiny/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CodewithJha/mutiny/releases/tag/v0.1.0
