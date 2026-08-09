# Changelog

All notable changes to Mutiny are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).  
Wheels are prepared as **`mutiny-ai`** (+ `mutiny-core`, `mutiny-openai-agents`) — first upload: [docs/PUBLISHING.md](./docs/PUBLISHING.md). Until then, versions refer to git tags / GitHub Releases.

## [Unreleased]

### Planned

- PyPI package publish (`pip install mutiny-ai`)
- Additional framework adapters (LangGraph, CrewAI, PydanticAI, …)
- Recorded demo GIF / Hosted screenshots under `docs/assets/`
- CI GitHub Action for sample-project `mutiny test` replay

## [0.1.0] — 2026-08-09

Initial public repository promotion.

### Added

- **Mutiny Core** — policy oracle, evolutionary campaign, minimize, regression replay (`packages/mutiny_core/`)
- **Adapter #1** — OpenAI Agents SDK (`packages/mutiny_openai_agents/`)
- **CLI** — `mutiny init` / `run` / `test` (`packages/mutiny_cli/`)
- **Sample project** — `examples/openai_support_agent/` (offline scripted model without API key)
- **Optional Hosted** — API (`apps/api/`) + UI (`apps/web/`) for campaign lineage
- Docs hub under `docs/`, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT
- CI workflow (unit tests) and good-first-issue catalog

### Notes

- Install from this repository with `uv sync --extra dev` (root `pip install -e .` is unsupported).
- Hosted UI is secondary; CLI with `--no-hosted` is the primary local path.
- Bundled sample / demo agents are **reference harnesses**, not the product.

[Unreleased]: https://github.com/CodewithJha/mutiny/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CodewithJha/mutiny/releases/tag/v0.1.0
