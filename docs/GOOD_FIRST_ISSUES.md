# Good First Issues

Maintainer catalog of **small, realistic** tasks for new contributors. Open GitHub issues labeled `good first issue` mirror the top items; this file is the longer backlog.

**Rules of the road:** do not redesign Core, campaigns, policies, or Hosted product architecture. Prefer docs, tests, CLI DX, a11y, examples, and thin adapter glue.

**How to pick one:** see [CONTRIBUTING.md](../CONTRIBUTING.md#good-first-issues--help-wanted). Comment on the GitHub issue before starting so nobody duplicates effort.

**Difficulty key:** `XS` ≈ &lt;1h docs/copy · `S` ≈ half day · `M` ≈ full day (still first-PR safe).

---

## Open on GitHub (labeled)

| GH | Catalog | Title | Difficulty | Primary files |
|---|---|---|---|---|
| [#1](https://github.com/CodewithJha/mutiny/issues/1) | #1 | Policy operator cheatsheet | S | `docs/POLICY_CHEATSHEET.md`, `docs/README.md`, `tests/unit/test_policy_*` |
| [#2](https://github.com/CodewithJha/mutiny/issues/2) | #2 | Document CLI flags from `--help` | S | `README.md` Commands, optional `docs/CLI.md` |
| [#3](https://github.com/CodewithJha/mutiny/issues/3) | #4 | Screenshot placeholders | XS | **Done for SVGs** — remaining: real PNG/GIF under `docs/assets/` |
| [#4](https://github.com/CodewithJha/mutiny/issues/4) | #9 | Skip-to-content / focus order | S | `apps/web` landing routes / layout |
| [#5](https://github.com/CodewithJha/mutiny/issues/5) | #15 | Policy evaluator edge cases | S | `tests/unit/test_policy_evaluator.py` |
| [#6](https://github.com/CodewithJha/mutiny/issues/6) | #21 | `mutiny init` next-step hint | XS | `packages/mutiny_cli/`, `tests/unit/test_mutiny_cli_init.py` |
| [#7](https://github.com/CodewithJha/mutiny/issues/7) | #28 | Comment headers in sample policy | XS | `examples/openai_support_agent/policy.yaml` |
| [#8](https://github.com/CodewithJha/mutiny/issues/8) | #37 | Document `/api/health` fields | S | `docs/` or `apps/api` README; `HealthResponse` in schemas |
| [#9](https://github.com/CodewithJha/mutiny/issues/9) | #24 | `dev.sh` node_modules hint | XS | `scripts/dev.sh` (tip may already exist — verify + docs) |
| [#10](https://github.com/CodewithJha/mutiny/issues/10) | #27 | Second email-domain policy example | S | `examples/policies/` |

---

## Docs (1–8)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 1 | Policy.yaml operator cheatsheet | S | Add `docs/POLICY_CHEATSHEET.md` with operators + examples from `tests/unit/test_policy_*` and sample `policy.yaml`; link from `docs/README.md` map; no language redesign | `docs/POLICY_CHEATSHEET.md`, `docs/README.md`, `tests/unit/test_policy_*.py`, `examples/openai_support_agent/policy.yaml` | `docs` `good first issue` |
| 2 | Document CLI flags from `--help` | S | Expand README Commands or add `docs/CLI.md` listing real flags from `uv run mutiny {init,run,test} --help`; keep install path honest (from source) | `README.md`, optional `docs/CLI.md` | `docs` `cli` |
| 3 | Honest PyPI wording in pitch docs | XS | Any remaining “`pip install mutiny` as available today” lines say from-source / planned | `docs/DEMO_SCRIPT.md`, `docs/DEVPOST.md`, `docs/PRD.md` | `docs` |
| 4 | Screenshot / GIF assets | XS–S | SVG placeholders ship under `docs/assets/`; **remaining:** real `*.png` / `mutiny-demo.gif` + README path swap per `docs/assets/README.md` | `docs/assets/*`, `README.md` | `docs` `examples` |
| 5 | Cross-link sample vs demo harness | XS | Three short paragraphs linking sample agent ↔ `examples/demo` ↔ COLD_START | `examples/*/README.md`, `docs/COLD_START.md` | `docs` `examples` |
| 6 | FAQ: Windows / WSL notes | S | 3 bullets in README FAQ for `uv` / venv on Windows + WSL | `README.md` | `docs` |
| 7 | Adapter-author reading order | XS | 10–15 lines pointer section in ARCHITECTURE (no redesign) | `docs/ARCHITECTURE.md` | `docs` |
| 8 | Gloss ADR-017 / 018 in docs map | XS | One-line each in `docs/README.md` document map | `docs/README.md` | `docs` |

## Frontend / Hosted UI polish (9–14)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 9 | Skip-to-content / focus order | S | Skip link + sensible focus order on Hosted landing; **no** layout/brand redesign | `apps/web/src/app/**` | `frontend` `a11y` `good first issue` |
| 10 | `aria-live` for campaign status | S | Wire existing running/finished status string to live region | `apps/web` campaign UI | `frontend` `a11y` |
| 11 | Escape closes modal/drawer | S | Handler if modal exists; else document N/A in PR | `apps/web` | `frontend` `a11y` |
| 12 | `prefers-reduced-motion` | S | Wrap decorative transitions in `globals.css` | `apps/web/src/app/globals.css` | `frontend` `a11y` |
| 13 | Empty-state copy sample vs project | XS | Clearer empty copy on `/policies` or `/tests` | Hosted empty states | `frontend` `docs` |
| 14 | Favicon / title consistency | XS | Meta + title across routes | `apps/web` | `frontend` |

## Tests (15–20)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 15 | Policy operator edge cases | S | Cases for empty args / nested paths; `uv run pytest tests/unit/test_policy_evaluator.py -q` green | `tests/unit/test_policy_evaluator.py` | `tests` `good first issue` |
| 16 | SKIPPED regression path | S | Assert SKIPPED when fixture/agent missing | `tests/unit` / CLI tests | `tests` `cli` |
| 17 | Golden minimized conversation | S | One JSON under `examples/regressions/` + README blurb | `examples/regressions/` | `tests` `examples` |
| 18 | CLI init key asserts | S | Assert generated yaml keys in init test | `tests/unit/test_mutiny_cli_init.py` | `tests` `cli` |
| 19 | Wrong `AGENT_REF` error | S | One failing-path test with clear message | adapter / CLI tests | `tests` `backend` |
| 20 | Reliability docstring | XS | Document expected smoke output | `tests/reliability/` | `tests` `docs` |

## CLI / DX (21–26)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 21 | `mutiny init` next-step hint | XS | Print edit-adapter → `mutiny run --no-hosted` after success; test if practical | `packages/mutiny_cli/`, init tests | `cli` `good first issue` |
| 22 | Friendlier `mutiny test` counts | XS | Clear PASS/FAIL/SKIPPED summary line | CLI test command | `cli` |
| 23 | Missing `policy.yaml` warning | S | Actionable path in error | `packages/mutiny_cli/` run | `cli` |
| 24 | `dev.sh` npm install hint | XS | Tip when `node_modules` missing (verify existing tip; improve docs if enough) | `scripts/dev.sh`, `docs/COLD_START.md` | `cli` `docs` |
| 25 | Sample README always `uv run mutiny` | XS | Docs-only alignment | `examples/**/README.md` | `docs` `examples` `cli` |
| 26 | `mutiny --version` | S | Print package version from metadata | `packages/mutiny_cli/` | `cli` |

## Examples / policy packs (27–32)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 27 | Email recipient domain policy | S | Example policy + short README; mock-tools only | `examples/policies/` | `examples` `good first issue` |
| 28 | Comment headers in sample policy | XS | Comments only; YAML still valid for `mutiny run` | `examples/openai_support_agent/policy.yaml` | `examples` `docs` |
| 29 | Policy pack stubs | S | refund + delete stubs + README | `examples/policies/` | `examples` |
| 30 | Annotated violation trace | S | Static JSON + notes | `examples/traces/` | `examples` |
| 31 | Offline env var table | XS | Document `OPENAI_API_KEY`, `MUTINY_SAMPLE_OFFLINE` | sample README | `examples` `docs` |
| 32 | Where policy packs live | XS | Short CONTRIBUTING blurb | `CONTRIBUTING.md` | `docs` `examples` |

## a11y & UI copy (33–36)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 33 | Form label audit | S | Associated `<label>` / `htmlFor` | `apps/web` forms | `a11y` `frontend` |
| 34 | Contrast on safety banner | S | Token tweak only | Hosted CSS tokens | `a11y` `frontend` |
| 35 | Alt text for screenshots | XS | Once real images land | `README.md`, assets | `a11y` `docs` |
| 36 | Plain-language empty states | XS | “regression” → short sentence + docs link | Hosted copy | `frontend` `docs` |

## Backend / API docs (37–40)

| # | Title | Difficulty | Acceptance | Affected files | Labels |
|---|---|---|---|---|---|
| 37 | Document `/api/health` | S | Fields from `HealthResponse` (`status`, `api`, `db`, `model`, `version`, …) after `curl`; optional stable-key integration assert | `docs/`, `apps/api/.../schemas.py` | `backend` `docs` `good first issue` |
| 38 | OpenAPI descriptions | S | Docstrings on 2–3 public routes | `apps/api` | `backend` `docs` |
| 39 | Health JSON key assert | S | Integration test stable keys | `tests/integration` | `tests` `backend` |
| 40 | docker-compose vs `dev.sh` | XS | When to use which in COLD_START | `docs/COLD_START.md` | `docs` |

## Stretch-but-still-first (claim via issue first)

| # | Title | Notes | Labels |
|---|---|---|---|
| 41 | LangGraph stub package | `TargetAdapter` + `NotImplementedError` only | `help wanted` `backend` |
| 42 | CrewAI or PydanticAI stub | One package skeleton | `help wanted` |
| 43 | CI: sample `mutiny test` | After unit tests in workflow | `tests` `cli` |
| 44 | Record sample GIF | `docs/assets/mutiny-demo.gif` + README | `docs` `examples` |

---

## Context links

- [CONTRIBUTING.md](../CONTRIBUTING.md) — 30-minute path  
- [docs/README.md](./README.md) — docs hub  
- [docs/assets/README.md](./assets/README.md) — screenshot / GIF drop instructions  
- [CHANGELOG.md](../CHANGELOG.md) — Unreleased / 0.1.0  
- [COLD_START.md](./COLD_START.md) — clean-machine bootstrap  

## Maintainer notes

- Prefer opening **5–10** GitHub issues from the top of each category with `good first issue` + area label.
- Use `help wanted` for adapter stubs and CI that need design agreement.
- Close or unlabel items that ship; keep this file as the long backlog.
- When editing issues, include **Difficulty**, **Affected files**, **Acceptance**, and a link back here.
