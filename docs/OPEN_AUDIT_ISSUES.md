# Open audit issues

Lightweight index of GitHub issues filed from the Mutiny deep audit (findings MUT-001–MUT-068). This is **not** another audit.

Verified against repo `main` (`f552b23`, after contributor PRs #83–#86, #88, #89; #87 reverted in #90).

**How to pick work**

- [`help wanted`](https://github.com/CodewithJha/mutiny/labels/help%20wanted) — meaningful, well-defined engineering (auth, Core, Hosted, tests).
- [`good first issue`](https://github.com/CodewithJha/mutiny/labels/good%20first%20issue) — small, clearly scoped. Never used here for security architecture or core algorithm redesign.
- Prefer **one issue per PR**. Combined MUT-IDs in a title are still one contributor task.
- Do not treat “highly likely” items as confirmed exploits. Do not add exploit PoCs.
- Private/sensitive reports: [SECURITY.md](../SECURITY.md).

Existing issues that already covered a finding were **not** duplicated: redaction **[#16](https://github.com/CodewithJha/mutiny/issues/16)**, Dependabot/CODEOWNERS **[#20](https://github.com/CodewithJha/mutiny/issues/20)**, `mutiny --version` **[#26](https://github.com/CodewithJha/mutiny/issues/26)** (shipped).

**Shipped from later contributor PRs:** [#66](https://github.com/CodewithJha/mutiny/issues/66) / MUT-017 ([#83](https://github.com/CodewithJha/mutiny/pull/83)), [#79](https://github.com/CodewithJha/mutiny/issues/79) / MUT-037 ([#84](https://github.com/CodewithJha/mutiny/pull/84)), [#72](https://github.com/CodewithJha/mutiny/issues/72) / MUT-024 ([#85](https://github.com/CodewithJha/mutiny/pull/85)), [#73](https://github.com/CodewithJha/mutiny/issues/73) / MUT-025 ([#86](https://github.com/CodewithJha/mutiny/pull/86)), [#71](https://github.com/CodewithJha/mutiny/issues/71) / MUT-023 ([#88](https://github.com/CodewithJha/mutiny/pull/88); [#87](https://github.com/CodewithJha/mutiny/pull/87) was reverted in [#90](https://github.com/CodewithJha/mutiny/pull/90)), [#68](https://github.com/CodewithJha/mutiny/issues/68) / MUT-020 ([#89](https://github.com/CodewithJha/mutiny/pull/89)).

---

## Bugs

| Issue | Finding | Description |
|---|---|---|
| [#57](https://github.com/CodewithJha/mutiny/issues/57) | MUT-003, MUT-014, MUT-034 | `mutiny run` tracebacks on adapter/config errors; `ToolsNotObservableError` reports `generations_completed=0`; missing-policy copy differs from `mutiny test`. Related: [#27](https://github.com/CodewithJha/mutiny/issues/27). |
| [#58](https://github.com/CodewithJha/mutiny/issues/58) | MUT-004, MUT-005 | `OPENAI_API_KEY` selects Featherless mutator; garbage `MUTINY_LLM_TIMEOUT` 500s `/api/health`. |
| [#60](https://github.com/CodewithJha/mutiny/issues/60) | MUT-007 | Policies page still calls 410 FS APIs. Related empty-state copy: [#47](https://github.com/CodewithJha/mutiny/issues/47). |
| [#61](https://github.com/CodewithJha/mutiny/issues/61) | MUT-008, MUT-019 | Hosted minimize/save defaults to `refund_limit`; successful minimize overwrites original genome. Related name default: [#36](https://github.com/CodewithJha/mutiny/issues/36). |
| [#65](https://github.com/CodewithJha/mutiny/issues/65) | MUT-015, MUT-016 | `use_boundary_seeds` is a no-op; `elite_count >= population_size` silently stalls mutation. |
| [#67](https://github.com/CodewithJha/mutiny/issues/67) | MUT-018 | Ingest artifact `sha256` mismatch is `pass` (advertised integrity is a no-op). |
| [#69](https://github.com/CodewithJha/mutiny/issues/69) | MUT-021 | Second in-process project load can reuse the first project’s `agent` module. |

---

## Security

| Issue | Finding | Description |
|---|---|---|
| [#55](https://github.com/CodewithJha/mutiny/issues/55) | MUT-001, MUT-010 | Web UI injects `MUTINY_API_TOKEN`; compose publishes `:3000`; FastAPI `/docs` stay public. |
| [#56](https://github.com/CodewithJha/mutiny/issues/56) | MUT-002 | Next.js locked at 15.5.22 (patch floor 15.5.24). Mutiny-specific AVIF path not proven (MUT-056). |
| [#16](https://github.com/CodewithJha/mutiny/issues/16) *(existing)* | MUT-011 | Expand secret redaction keys / `sk-` patterns. |
| [#63](https://github.com/CodewithJha/mutiny/issues/63) | MUT-012 | Compose/Railway: root, install-at-boot, full-repo bind-mount. |
| [#64](https://github.com/CodewithJha/mutiny/issues/64) | MUT-013 | Pin Actions to SHAs; least-privilege CI `permissions`. Dependabot/CODEOWNERS already [#20](https://github.com/CodewithJha/mutiny/issues/20). |
| [#80](https://github.com/CodewithJha/mutiny/issues/80) | MUT-041 | `--hosted` sends the token to any yaml `api_url` (highly likely; not reproduced against a listener). |

CSRF, `/_next/image` AVIF reachability, missing CSP, and similar items are **deferred** (needs verification). Do not file “confirmed vuln” PRs for those.

---

## Reliability

| Issue | Finding | Description |
|---|---|---|
| [#59](https://github.com/CodewithJha/mutiny/issues/59) | MUT-006 | Interrupted `--hosted` ingest leaves campaigns `running` and wedges demo starts (409). |
| [#70](https://github.com/CodewithJha/mutiny/issues/70) | MUT-022, MUT-045 | `wall_clock_seconds` is generation-granular; no timeout around `adapter.step`. |
| [#82](https://github.com/CodewithJha/mutiny/issues/82) | MUT-043, MUT-044, MUT-053 | SSE snapshot-then-subscribe race; shared SQLite `check_same_thread=False`; disconnect/ping untested. Highly likely, not load-reproduced. |

---

## Testing and CI

| Issue | Finding | Description |
|---|---|---|
| [#74](https://github.com/CodewithJha/mutiny/issues/74) | MUT-026 | Hosted UI has zero tests (tsc/build only). |
| [#75](https://github.com/CodewithJha/mutiny/issues/75) | MUT-027, MUT-048, MUT-052 | Weak CLI/loader unit coverage; reliability job is boundary-seed smoke; extract tests JSON-string only. |
| [#76](https://github.com/CodewithJha/mutiny/issues/76) | MUT-028, MUT-040 | Python CI is pytest-only (no ruff gate); PR template asks for unit tests only. |

Branch protection on `main` (MUT-029) is maintainer-only — not filed for contributors.

---

## Documentation and DX

| Issue | Finding | Description |
|---|---|---|
| [#62](https://github.com/CodewithJha/mutiny/issues/62) | MUT-009, MUT-054, MUT-065 | Sample/init/`/api/meta`/system diagram still describe Hosted `project_path` exec. Related empty `integrations/`: [#38](https://github.com/CodewithJha/mutiny/issues/38). |
| [#77](https://github.com/CodewithJha/mutiny/issues/77) | MUT-030, MUT-031, MUT-032, MUT-033, MUT-064 | Sample FAIL→fix undocumented; FAQ talks as if 0.2.0 unpublished; CLI.md/ARCHITECTURE lag; two visual canons; git vs PyPI policy coercion. |
| [#78](https://github.com/CodewithJha/mutiny/issues/78) | MUT-035, MUT-050, MUT-051 | Root/API version 0.1.0 vs packages 0.2.0; 3.13 classifier without CI; `mutiny db` advertised on PyPI CLI. |
| [#26](https://github.com/CodewithJha/mutiny/issues/26) *(shipped)* | MUT-038 | `mutiny --version` — already on `main`. |

---

## Architecture / packaging

| Issue | Finding | Description |
|---|---|---|
| [#81](https://github.com/CodewithJha/mutiny/issues/81) | MUT-042 | PyPI `openai-agents>=0.19` floats past the workspace lock (highly likely drift). |

Demo process globals (MUT-046) were skipped: Hosted concurrency is 1 and CLI is sequential.

---

## Not filed (on purpose)

| IDs | Why |
|---|---|
| MUT-029 | Maintainer GitHub setting (required checks). |
| MUT-036, MUT-039, MUT-047 | Low value or already noted on a related issue. |
| MUT-049, MUT-055–MUT-058, MUT-060–MUT-063, MUT-066 | Needs verification — not scheduled as bugs. |
| MUT-057 | Already documented in SECURITY.md (raw uvicorn bind). |
| MUT-059 | Accepted single-tenant ingest IDs. Related attestation work: [#32](https://github.com/CodewithJha/mutiny/issues/32). |
| MUT-067, MUT-068 | Informational documented trust models — not bugs. |

Full mapping lives in the audit-to-issues filing notes (conversation / maintainer summary). Source of truth for remaining work: the GitHub issues above.
