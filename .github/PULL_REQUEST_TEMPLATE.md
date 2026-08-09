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

<!-- Commands you ran, or “docs-only / N/A” -->

```bash
uv sync --extra dev
uv run pytest tests/unit -q
```
