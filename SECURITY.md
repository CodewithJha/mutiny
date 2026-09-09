# Security Policy

## Supported versions

Mutiny is under active development. Security fixes land on `main` first. There is no separate LTS branch yet.

| Version / branch | Supported |
|---|---|
| `main` (latest) | Yes |
| Older commits / forks | Best-effort |

## What Mutiny is (and isn’t)

Mutiny is a **behavioral fuzz-testing engine** for agents you own or are authorized to test. It is **not** an open-internet attack proxy. Default targets are local projects, in-process adapters, or localhost with sandboxed mock tools.

## Hosted execution (M-PR1)

| Path | Behavior |
|---|---|
| **Local CLI** (`mutiny run`, `mutiny test`) | Executes the project's `.mutiny/adapter.py` in-process. Intentional — same trust model as running project tests. Default `mutiny run` path (M-PR2). |
| **Hosted trusted harness** (`target=in_process_demo`) | Uses the bundled demo agent only. No customer `project_path` import. |
| **Hosted customer project** (`target=openai_agents` + `project_path`) | **Disabled by default.** The API returns `403 project_exec_disabled` and does not import/execute customer Python. |

Operators who accept the risk on a **single-operator localhost** machine may set `MUTINY_ALLOW_PROJECT_EXEC=1`. That flag is **not** a sandbox and **not** authorization. Do not expose Hosted on a shared or public network with this flag enabled.

**Target architecture (ADR-019 accepted; M-PR8 in progress):** Hosted is **observe/lineage only** for customer projects — customer `.mutiny/adapter.py` executes on the Local CLI trust domain; the shared API process must not `exec_module` customer trees in Production Hosted. **M-PR8B** ships authenticated `/api/ingest/v1/*` (data only). Until M-PR8E, treat any Hosted customer exec path as localhost-only opt-in debt.

**Ingestion (M-PR8A–D):** CLI → Hosted uploads send **already-redacted** JSON evidence (data, not executable). See [docs/HOSTED_INGESTION.md](./docs/HOSTED_INGESTION.md). Hosted ingest API + CLI `--hosted` local-exec sync + Web observe-only copy are implemented; production customer `exec_module` removal remains M-PR8E.

## Hosted authentication (M-PR7)

Single-tenant shared Bearer token for the Hosted **control plane** (not multi-user accounts, OAuth, sessions, or RBAC).

| Setting | Behavior |
|---|---|
| `MUTINY_API_TOKEN` **unset** / empty | Auth disabled — local demo / tests only. Do not expose on a shared network. |
| `MUTINY_API_TOKEN` **set** | Protected `/api/*` routes require `Authorization: Bearer <token>`. Missing/invalid → `401 unauthorized`. |

**Public (intentionally):** `GET /api/health`, `GET /api/meta` (meta reports `safety.auth_required` / `auth_env` — never the token value).

**Protected:** campaigns, SSE/events, projects, policies, candidates, minimize, regressions, tests.

CLI: default `mutiny run` stays local and needs no token. Explicit `mutiny run --hosted` / `--hosted-url` sends `MUTINY_API_TOKEN` when set; if the API requires auth and the token is missing/invalid, the CLI fails closed (no silent local fallback).

**Auth ≠ sandbox:** A valid token does **not** enable customer `project_path` adapter execution and does **not** bypass M-PR1. ADR-021 auth and ADR-019 observe-only isolation are orthogonal; M-PR8 implements ADR-019.

## Secret redaction (M-PR3)

Mutiny applies a **small, deterministic, local** redactor (`mutiny_core.redact.redact_secrets`) before durable/user-visible evidence surfaces:

| Covered | Examples |
|---|---|
| Credential field values (case-insensitive keys) | `api_key` / `apiKey`, `token`, `password` / `passwd`, `secret`, `access_token`, `refresh_token`, `authorization` |
| Inline Authorization headers | `Authorization: Bearer …` inside strings |

**Where:** campaign event dumps (trace/hits), Hosted SQLite persistence (traces, hits, event payloads, test-run evidence), Hosted API responses fed from those stores, CLI `mutiny test` evidence / reports.

**Boundary:** raw runtime traces remain available in-memory for `PolicyEvaluator` / fitness / minimize. Redaction runs on serialized persist/display copies. Marker: `[REDACTED]`.

**Not a guarantee:** Mutiny does **not** detect every possible secret format (no LLM / external scanner). Unusual encodings, custom header schemes, and secrets embedded only in attack genomes may still appear. Rollback: `MUTINY_DISABLE_SECRET_REDACTION=1`.

## Hosted SQLite path (M-PR4)

Hosted API persistence uses a single SQLite file resolved by `mutiny_api.db.resolve_db_path`:

| Precedence | Source |
|---|---|
| 1 | Explicit `create_app(db_path=…)` (tests / programmatic) |
| 2 | `MUTINY_DB_PATH` environment variable |
| 3 | Default `data/mutiny.sqlite` |

Parent directories are created when missing. Empty or unusable paths **fail closed** — Mutiny does **not** silently open another database. `docker-compose.yml` sets `MUTINY_DB_PATH=/app/data/mutiny.sqlite` and the API uses that path.

**Not provided:** automated backup/export/restore. Operators own filesystem snapshots of the configured SQLite file. Ephemeral deploy disks (e.g. Railway without a volume) remain a data-loss risk.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

1. Prefer [GitHub Security Advisories](https://github.com/CodewithJha/mutiny/security/advisories/new) (private disclosure).
2. Or email the maintainer via the contact options on the [GitHub profile](https://github.com/CodewithJha) linked from this repository.

Include:

- Affected package / path (`mutiny_core`, CLI, Hosted API/UI, adapter, …)
- Steps to reproduce
- Impact (data exposure, RCE on Hosted, policy bypass in the oracle, …)
- Whether you have a suggested fix

We aim to acknowledge within **7 days** and share a remediation plan when we have one.

## Safe contribution rules

- Do not commit secrets, API keys, or production credentials.
- Do not add features that encourage testing third-party systems without attestation / authorization.
- Prefer local / mock tools in examples and tests.

## Scope notes for researchers

In-scope examples: flaws in policy evaluation, regression replay correctness, Hosted API auth gaps (when auth exists), dependency CVEs in this repo’s lockfiles.

Out of scope: using Mutiny to attack systems you do not own; social engineering of maintainers; DoS against GitHub infrastructure.
