# Good First Issues

Maintainer catalog of **small, realistic** tasks for new contributors. Many are labeled `good first issue` / `help wanted` on GitHub when opened; the rest stay here as a backlog seed.

**Rules of the road:** do not redesign Core, campaigns, policies, or Hosted product architecture. Prefer docs, tests, CLI DX, a11y, examples, and thin adapter glue.

**How to pick one:** see [CONTRIBUTING.md](../CONTRIBUTING.md#good-first-issues--help-wanted). Claim an open GitHub issue (or open one from this list) before a large PR.

---

## Docs (1–8)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 1 | Add a one-page “policy.yaml cheatsheet” under `docs/` with operator examples from tests | Copy from `tests/unit/test_policy_*` + sample policy | `docs` `good first issue` |
| 2 | Document every `mutiny run` / `init` / `test` CLI flag in README Commands (mirror `--help`) | Run `uv run mutiny --help` and subcommands | `docs` `cli` |
| 3 | Fix remaining “`pip install mutiny`” pitch lines in `docs/DEMO_SCRIPT.md` / `DEVPOST.md` to say “from source today; PyPI planned” | Search + replace with honesty | `docs` |
| 4 | Add Screenshots placeholders under `docs/assets/` + README captions (CLI terminal, Hosted campaign, policy file) | Create dirs + markdown image slots | `docs` `examples` |
| 5 | Cross-link `examples/demo/README.md` ↔ sample agent ↔ COLD_START so harness vs customer path is obvious | Three short paragraphs | `docs` `examples` |
| 6 | Expand FAQ: Windows `uv` / venv activation; WSL notes | Reproduce once, write 3 bullets | `docs` |
| 7 | Add “Reading order for adapter authors” section to `docs/ARCHITECTURE.md` (pointer only) | 10–15 lines, no redesign | `docs` |
| 8 | Gloss ADR titles in `docs/README.md` document map (one-line each for ADR-017 / 018) | Link + one sentence | `docs` |

## Frontend / Hosted UI polish (9–14)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 9 | Ensure skip-to-content / focus order on Hosted landing (`apps/web`) | a11y pass, no layout redesign | `frontend` `a11y` `good first issue` |
| 10 | Add visible `aria-live` status for campaign “running / finished” text already on screen | Wire existing status string | `frontend` `a11y` |
| 11 | Keyboard: Escape closes any existing modal/drawer if present; document if not | Audit + small handler | `frontend` `a11y` |
| 12 | Prefer `prefers-reduced-motion` for decorative CSS transitions in `globals.css` | Media query wrap | `frontend` `a11y` |
| 13 | Empty-state copy on `/policies` or `/tests` when lists are empty — clearer “sample vs your project” | Copy-only | `frontend` `docs` |
| 14 | Favicon / page title consistency across Hosted routes | Meta + title | `frontend` |

## Tests (15–20)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 15 | Add unit cases for a policy operator edge (empty args, nested paths) in `tests/unit/test_policy_evaluator.py` | Mirror existing patterns | `tests` `good first issue` |
| 16 | Regression replay: assert SKIPPED path when fixture missing / agent unavailable | Extend `test_regression.py` / CLI test | `tests` `cli` |
| 17 | Golden fixture: one minimized conversation JSON under `examples/regressions/` with README blurb | File + 5-line doc | `tests` `examples` |
| 18 | CLI init: assert generated `policy.yaml` / `mutiny.yaml` keys in `test_mutiny_cli_init.py` | Snapshot-style asserts | `tests` `cli` |
| 19 | Adapter runner: cover error message when `AGENT_REF` is wrong | One failing path test | `tests` `backend` |
| 20 | Reliability: document expected smoke output in `tests/reliability/` docstring | Docstring only or assert message | `tests` `docs` |

## CLI / DX (21–26)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 21 | `mutiny init`: print next-step hint (`edit adapter.py` → `mutiny run --no-hosted`) | One echo after write | `cli` `good first issue` |
| 22 | `mutiny test`: friendlier summary line counts (PASS/FAIL/SKIPPED) | Format string | `cli` |
| 23 | Refuse / warn if `mutiny run` cwd has no `policy.yaml` with actionable path | Early check | `cli` |
| 24 | `scripts/dev.sh`: print `npm install` hint when `apps/web/node_modules` missing | Guard before `npm run dev` | `cli` `docs` |
| 25 | Align sample README commands to always show `uv run mutiny …` | Docs-only in examples | `docs` `examples` `cli` |
| 26 | Add `mutiny --version` if missing (package version from metadata) | Tiny CLI change | `cli` |

## Examples / policy packs (27–32)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 27 | Second example `policy.yaml` for “email requires confirmed recipient domain” | Copy sample style | `examples` `good first issue` |
| 28 | Comment headers in `examples/openai_support_agent/policy.yaml` explaining each rule | Comments only | `examples` `docs` |
| 29 | `examples/policies/` pack: refund approval + delete confirm stubs with README | YAML + README | `examples` |
| 30 | Trace example JSON under `examples/traces/` with annotation of a violation | Static file | `examples` |
| 31 | Document offline model env vars in sample README table (`OPENAI_API_KEY`, `MUTINY_SAMPLE_OFFLINE`) | Table already partial | `examples` `docs` |
| 32 | Tiny “policy pack” CONTRIBUTING blurb: where packs should live | Docs | `docs` `examples` |

## a11y & UI copy (33–36)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 33 | Audit Hosted forms for associated `<label>` / `htmlFor` | Spot-fix missing labels | `a11y` `frontend` |
| 34 | Color contrast pass on safety banner / secondary text | Token tweak only | `a11y` `frontend` |
| 35 | Alt text for any decorative vs informative images once screenshots land | Markdown / img alt | `a11y` `docs` |
| 36 | Reduce jargon in Hosted empty states (“regression” → short plain sentence + link to docs) | Copy | `frontend` `docs` |

## Backend / API docs (37–40)

| # | Title | Why it’s small | Labels |
|---|---|---|---|
| 37 | Document `/api/health` response fields in `docs/` or API README | Observe once with curl | `backend` `docs` `good first issue` |
| 38 | OpenAPI / FastAPI description strings for 2–3 public routes | Docstrings | `backend` `docs` |
| 39 | Integration test assert health JSON keys stay stable | One assert block | `tests` `backend` |
| 40 | Clarify docker-compose vs `scripts/dev.sh` in COLD_START (when to use which) | Docs | `docs` |

## Stretch-but-still-first (claim via issue first)

| # | Title | Notes | Labels |
|---|---|---|---|
| 41 | Scaffold empty `packages/mutiny_langgraph/` with README + `TargetAdapter` stub raising `NotImplementedError` | Interface only — no Core changes | `help wanted` `backend` |
| 42 | Same stub for CrewAI or PydanticAI | One package skeleton | `help wanted` |
| 43 | GitHub Action: run `uv run mutiny test` in sample project after unit tests | CI YAML | `tests` `cli` |
| 44 | Record asciinema / GIF of sample `mutiny run --no-hosted` | Asset + README link | `docs` `examples` |

---

## Maintainer notes

- Prefer opening **5–10** GitHub issues from the top of each category with `good first issue` + area label.
- Use `help wanted` for adapter stubs and CI that need design agreement.
- Close or unlabel items that are done; keep this file as the long backlog.
