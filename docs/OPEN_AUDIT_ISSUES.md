# Open audit issues

Lightweight index of GitHub issues filed from the Mutiny deep audit (findings MUT-001–MUT-068). This is **not** another audit.

Verified against repo `main` (`8724f9f`, after contributor PRs #83–#86, #88, #89, #91–#100, #118, #119, #122–#125, #127, #133, #135, #137; #87 reverted in #90).

**How to pick work**

- [`help wanted`](https://github.com/CodewithJha/mutiny/labels/help%20wanted) — meaningful, well-defined engineering (auth, Core, Hosted, tests).
- [`good first issue`](https://github.com/CodewithJha/mutiny/labels/good%20first%20issue) — small, clearly scoped. Never used here for security architecture or core algorithm redesign.
- Prefer **one issue per PR**. Combined MUT-IDs in a title are still one contributor task.
- Do not treat “highly likely” items as confirmed exploits. Do not add exploit PoCs.
- Private/sensitive reports: [SECURITY.md](../SECURITY.md).

Existing issues that already covered a finding were **not** duplicated: redaction **[#16](https://github.com/CodewithJha/mutiny/issues/16)**, Dependabot/CODEOWNERS **[#20](https://github.com/CodewithJha/mutiny/issues/20)** (shipped in [#99](https://github.com/CodewithJha/mutiny/pull/99)), `mutiny --version` **[#26](https://github.com/CodewithJha/mutiny/issues/26)** (shipped).

**Shipped from later contributor PRs:** [#66](https://github.com/CodewithJha/mutiny/issues/66) / MUT-017 ([#83](https://github.com/CodewithJha/mutiny/pull/83)), [#79](https://github.com/CodewithJha/mutiny/issues/79) / MUT-037 ([#84](https://github.com/CodewithJha/mutiny/pull/84)), [#72](https://github.com/CodewithJha/mutiny/issues/72) / MUT-024 ([#85](https://github.com/CodewithJha/mutiny/pull/85)), [#73](https://github.com/CodewithJha/mutiny/issues/73) / MUT-025 ([#86](https://github.com/CodewithJha/mutiny/pull/86)), [#71](https://github.com/CodewithJha/mutiny/issues/71) / MUT-023 ([#88](https://github.com/CodewithJha/mutiny/pull/88); [#87](https://github.com/CodewithJha/mutiny/pull/87) was reverted in [#90](https://github.com/CodewithJha/mutiny/pull/90)), [#68](https://github.com/CodewithJha/mutiny/issues/68) / MUT-020 ([#89](https://github.com/CodewithJha/mutiny/pull/89)), [#57](https://github.com/CodewithJha/mutiny/issues/57) / MUT-003, MUT-014, MUT-034 ([#91](https://github.com/CodewithJha/mutiny/pull/91)), [#67](https://github.com/CodewithJha/mutiny/issues/67) / MUT-018 ([#93](https://github.com/CodewithJha/mutiny/pull/93)), [#82](https://github.com/CodewithJha/mutiny/issues/82) / MUT-043, MUT-044, MUT-053 ([#92](https://github.com/CodewithJha/mutiny/pull/92)), [#80](https://github.com/CodewithJha/mutiny/issues/80) / MUT-041 ([#94](https://github.com/CodewithJha/mutiny/pull/94)), [#64](https://github.com/CodewithJha/mutiny/issues/64) / MUT-013 ([#95](https://github.com/CodewithJha/mutiny/pull/95)), [#70](https://github.com/CodewithJha/mutiny/issues/70) / MUT-022, MUT-045 ([#96](https://github.com/CodewithJha/mutiny/pull/96)), [#65](https://github.com/CodewithJha/mutiny/issues/65) / MUT-015, MUT-016 ([#97](https://github.com/CodewithJha/mutiny/pull/97)), [#56](https://github.com/CodewithJha/mutiny/issues/56) / MUT-002 ([#100](https://github.com/CodewithJha/mutiny/pull/100)), [#76](https://github.com/CodewithJha/mutiny/issues/76) / MUT-028, MUT-040 ([#118](https://github.com/CodewithJha/mutiny/pull/118)), [#59](https://github.com/CodewithJha/mutiny/issues/59) / MUT-006 ([#98](https://github.com/CodewithJha/mutiny/pull/98)), [#69](https://github.com/CodewithJha/mutiny/issues/69) / MUT-021 ([#119](https://github.com/CodewithJha/mutiny/pull/119)), [#78](https://github.com/CodewithJha/mutiny/issues/78) / MUT-035, MUT-050, MUT-051 ([#122](https://github.com/CodewithJha/mutiny/pull/122)), [#58](https://github.com/CodewithJha/mutiny/issues/58) / MUT-004, MUT-005 ([#125](https://github.com/CodewithJha/mutiny/pull/125)), [#61](https://github.com/CodewithJha/mutiny/issues/61) / MUT-008, MUT-019 ([#123](https://github.com/CodewithJha/mutiny/pull/123)), [#77](https://github.com/CodewithJha/mutiny/issues/77) / MUT-030–033, MUT-064 ([#124](https://github.com/CodewithJha/mutiny/pull/124)), [#62](https://github.com/CodewithJha/mutiny/issues/62) / MUT-009, MUT-054, MUT-065 ([#127](https://github.com/CodewithJha/mutiny/pull/127)), [#60](https://github.com/CodewithJha/mutiny/issues/60) / MUT-007 ([#137](https://github.com/CodewithJha/mutiny/pull/137)), [#63](https://github.com/CodewithJha/mutiny/issues/63) / MUT-012 ([#135](https://github.com/CodewithJha/mutiny/pull/135)).

---

## Bugs

No open audit bugs. Policies page (#60) shipped in #137.

---

## Security

| Issue | Finding | Description |
|---|---|---|
| [#55](https://github.com/CodewithJha/mutiny/issues/55) | MUT-001, MUT-010 | Web UI injects `MUTINY_API_TOKEN`; compose publishes `:3000`; FastAPI `/docs` stay public. |
| [#16](https://github.com/CodewithJha/mutiny/issues/16) *(existing)* | MUT-011 | Expand secret redaction keys / `sk-` patterns. |

CSRF, `/_next/image` AVIF reachability, missing CSP, and similar items are **deferred** (needs verification). Do not file “confirmed vuln” PRs for those.

---

## Testing and CI

| Issue | Finding | Description |
|---|---|---|
| [#74](https://github.com/CodewithJha/mutiny/issues/74) | MUT-026 | Hosted UI has zero tests (tsc/build only). |
| [#75](https://github.com/CodewithJha/mutiny/issues/75) | MUT-027, MUT-048, MUT-052 | Weak CLI/loader unit coverage; reliability job is boundary-seed smoke; extract tests JSON-string only. |

Branch protection on `main` (MUT-029) is maintainer-only — not filed for contributors.

---

## Documentation and DX

| Issue | Finding | Description |
|---|---|---|
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
| MUT-059 | Accepted single-tenant ingest IDs. Attestation timestamps shipped in [#32](https://github.com/CodewithJha/mutiny/issues/32) (PR #133). |
| MUT-067, MUT-068 | Informational documented trust models — not bugs. |

Full mapping lives in the audit-to-issues filing notes (conversation / maintainer summary). Source of truth for remaining work: the GitHub issues above.
