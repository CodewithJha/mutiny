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

Operators who accept the risk on a **single-operator localhost** machine may set `MUTINY_ALLOW_PROJECT_EXEC=1`. That flag is **not** a sandbox and **not** authorization. Do not expose Hosted on a shared or public network with this flag enabled. Full Hosted isolation remains an ADR-019 decision.

## Secret redaction (M-PR3)

Mutiny applies a **small, deterministic, local** redactor (`mutiny_core.redact.redact_secrets`) before durable/user-visible evidence surfaces:

| Covered | Examples |
|---|---|
| Credential field values (case-insensitive keys) | `api_key` / `apiKey`, `token`, `password` / `passwd`, `secret`, `access_token`, `refresh_token`, `authorization` |
| Inline Authorization headers | `Authorization: Bearer …` inside strings |

**Where:** campaign event dumps (trace/hits), Hosted SQLite persistence (traces, hits, event payloads, test-run evidence), Hosted API responses fed from those stores, CLI `mutiny test` evidence / reports.

**Boundary:** raw runtime traces remain available in-memory for `PolicyEvaluator` / fitness / minimize. Redaction runs on serialized persist/display copies. Marker: `[REDACTED]`.

**Not a guarantee:** Mutiny does **not** detect every possible secret format (no LLM / external scanner). Unusual encodings, custom header schemes, and secrets embedded only in attack genomes may still appear. Rollback: `MUTINY_DISABLE_SECRET_REDACTION=1`.

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
