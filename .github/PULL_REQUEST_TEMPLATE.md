## Summary

<!-- What changed and why (1–3 bullets). Link related issues: Fixes #NN -->

## Type of change

- [ ] Docs / community / DX only
- [ ] Bug fix
- [ ] Tests
- [ ] CLI / DX
- [ ] Adapter (new or Adapter #1)
- [ ] Core engine (policy, campaign, minimize, regression)
- [ ] Hosted API / UI (secondary surface)

## Checklist

- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md) (where to ask, how reviews work, how to run tests)
- [ ] Linked related issue (`Fixes #N`) or Discussion when applicable
- [ ] Core stays free of framework SDK imports (adapters own glue)
- [ ] Tests added or updated when behavior changes (`uv run pytest tests/unit -q`)
- [ ] Docs / README claims match reality (no PyPI / multi-adapter claims unless shipped)
- [ ] One concern per PR when possible
- [ ] Authorized testing only — no open-internet attack-proxy behavior

## Test plan

<!-- CI runs every job below. Record the local checks you ran and explain any
     omissions; do not mark an unrun check as passed. Setup: uv sync --extra dev.
     See CONTRIBUTING.md for prerequisites, offline sample setup and details. -->

- [ ] Python lint: `uv run ruff check`
- [ ] Backend tests (CI: Python 3.11 and 3.12): `MUTINY_SAMPLE_OFFLINE=1 uv run pytest tests/unit tests/integration tests/reliability -q`
- [ ] CLI smoke: from `examples/openai_support_agent`, run `uv run mutiny --help`, `uv run mutiny init`, and `uv run mutiny run` with `MUTINY_SAMPLE_OFFLINE=1` and empty `OPENAI_API_KEY` / `FEATHERLESS_API_KEY`.
- [ ] Web typecheck + build (CI: Node 20): from `apps/web`, run `npm ci`, `npx tsc --noEmit`, and `npm run build`.
- [ ] Package build + isolated artifact gate: `uv run pytest tests/unit/test_package_release.py -q` and `./scripts/verify_release_artifacts.sh`.

<!-- Include commands/results and any checks left for CI here. -->
