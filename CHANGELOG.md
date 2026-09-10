# Changelog

All notable changes to Mutiny are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).  
Published on PyPI as **`mutiny-ai`** (+ [`mutiny-core`](https://pypi.org/project/mutiny-core/), [`mutiny-openai-agents`](https://pypi.org/project/mutiny-openai-agents/)) — see [docs/PUBLISHING.md](./docs/PUBLISHING.md).

## [Unreleased]

### Planned

- Additional framework adapters (LangGraph, CrewAI, PydanticAI, …)
- Dedicated GitHub Action for customer-project `mutiny test` replay packaging (sample path covered by CLI smoke + suites)
- Multi-tenant / SaaS Hosted, distributed rate limits, AuthZ beyond attestation

## [0.2.0] — 2026-09-10

**Production Local CLI release candidate.** Primary surface: `pip install mutiny-ai` → `mutiny init` / `run` / `test` on a developer machine. Hosted remains optional observe/lineage (not multi-tenant Production Hosted).

### Supported in 0.2.0

#### Local CLI (primary)

- Install **`mutiny-ai`** from PyPI without monorepo `uv sync` or Hosted
- `mutiny init` scaffolds `.mutiny/adapter.py`, `policy.yaml`, `mutiny.yaml`
- `mutiny run` defaults to **local** Core + Adapter #1 (OpenAI Agents SDK); Hosted only via `--hosted` / `--hosted-url` (M-PR2)
- Offline sample path (`examples/openai_support_agent`, `MUTINY_SAMPLE_OFFLINE`)

#### Deterministic policy & search

- Deterministic policy oracle on tool-call traces (`deny_tool` / `require_args` / `forbid_args`) — no LLM judge for acceptance
- Policy-derived campaign seeds and template/LLM mutators via `AttackFocus` (M-PR6 / ADR-020); refund corpora remain demo/harness helpers only

#### Minimize, regressions, redaction

- Minimize with re-exec gate; save under `.mutiny/tests/`
- `mutiny test` FAIL → PASS after a documented agent fix
- Deterministic secret redaction on persist/display paths (M-PR3); not a general secret scanner

#### Hosted (observe-only; secondary)

- `mutiny run --hosted` = local adapter execution + redacted ingest sync (ADR-019 / M-PR8A–E)
- Customer Hosted `project_path` adapter `exec_module` permanently removed (`410 hosted_customer_execution_removed`; `MUTINY_ALLOW_PROJECT_EXEC` ignored) (M-PR8E)
- Customer `project_path` filesystem-inert / opaque on Hosted (`410 hosted_filesystem_access_removed`) (P0-3)
- Single-tenant Bearer auth (`MUTINY_API_TOKEN`); non-loopback binds fail closed without token (M-PR7 / P0-1 / P0-4)
- In-process Hosted rate limits when auth is configured (P1-2; not distributed)
- Operator SQLite backup/restore: `mutiny db backup` / `mutiny db restore` (P2-6; requires Hosted `mutiny-api` / workspace — not an HTTP API, not off-site automation)
- `MUTINY_DB_PATH` honored for Hosted SQLite (M-PR4)

#### Packaging & release integrity

- Aligned **`0.2.0`** for `mutiny-core` / `mutiny-openai-agents` / `mutiny-ai`
- Runtime `mutiny_core.__version__` from package metadata (not a hardcoded release string)
- Sibling deps require `>=0.2.0` so installs do not resolve stale `0.1.x` from PyPI when publishing together
- PR CI `package-build` + `./scripts/verify_release_artifacts.sh`: build wheels from current source → isolated venv install (sibling wheels together) → offline Local CLI smoke
- Publish workflow verifies artifacts before upload; refuses silent “success” when a version is already on PyPI

#### Security hardening (shipped in this line)

- M-PR8E / P0-3 / P0-1 / P0-4 / P1-2 as above; Local CLI adapter loading unchanged

### Not part of 0.2.0

- Multi-tenant / SaaS Hosted, org SSO, or AuthZ beyond checkbox attestation (P1-1 open)
- Distributed / multi-replica rate limits
- Additional framework adapters (LangGraph, CrewAI, PydanticAI, AutoGen, HTTP)
- Consumer GitHub Action for customer-project CI packaging
- Policy packs library; Postgres; K8s / worker fleets
- Claiming Production Hosted (Target B) or public multi-tenant deploy

### Notes

- PyPI may still show **`0.1.0`** until this version is published — do not treat editable/`uv sync` success as PyPI readiness.
- Hosted UI/API remain optional secondary surfaces; primary path needs no Hosted process.

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

[Unreleased]: https://github.com/CodewithJha/mutiny/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/CodewithJha/mutiny/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/CodewithJha/mutiny/releases/tag/v0.1.0
