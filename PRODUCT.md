# Product

<!-- impeccable:product-schema 1 -->

## Platform

cli + web

## Users

Primary: developers building AI agents who install Mutiny locally (`mutiny init` → `mutiny run`; PyPI publish planned) to fuzz tool-use policies and freeze failures as regressions. Current scope assumes their project uses the **OpenAI Agents SDK** (Adapter #1).

Secondary: AI/security engineers replaying regressions in CI; contributors and operators viewing Hosted lineage against a **sample** agent project (bundled demo as reference harness).

## Product Purpose

**Mutiny is a behavioral fuzz-testing engine for AI agents.** Developers point it at **their own** agent; Mutiny searches for conversations that violate explicit tool-use policies, proves breaks on traces, minimizes, and saves permanent regression tests.

**What's included today:** support for OpenAI Agents SDK projects through Adapter #1 on a framework-neutral Core.

**Success criteria:** a developer with an OpenAI Agents SDK project can init Mutiny, connect via adapter, run a campaign, and get a verified violation → minimized regression — optionally inspect lineage in Hosted UI.

## Positioning

AFL for agent tool policies — a framework-neutral engine with adapters. Deterministic tool-arg oracle + evolutionary search + regression artifacts — not a jailbreak catalog, not LLM-as-judge CI, not “host our vulnerable demo agent” as the product, and not “an OpenAI Agents SDK testing tool.”

## Operating Context

Local install into the customer project (adapter + `policy.yaml` + `mutiny.yaml`). Core runs campaigns against the adapter layer. Hosted API/UI remains an ops/visualization surface. Bundled demo agent is a **reference implementation / sample target / docs example**, not the primary user workflow. Docs in `docs/`. Demo spine in DEMO_SCRIPT. Cold start in COLD_START.

## Capabilities

- `mutiny init` — scaffold `.mutiny/adapter.py`, `policy.yaml`, `mutiny.yaml`
- Connect a local agent via adapter (Adapter #1: OpenAI Agents SDK)
- Discover tool calls; run evolutionary campaigns
- Deterministic violation proof on tool-call traces
- Minimize + save regression + replay FAIL/PASS
- Optional Hosted UI: campaign progress, lineage, evidence

## Constraints

- Authorized testing only; mock / sandboxed tools for demos; local project or localhost
- First production-quality adapter = **OpenAI Agents SDK** (other frameworks = roadmap adapters)
- Web talks to API only — no browser-side policy evaluation
- No multi-tenant auth in current scope
- Honest competitive claims (see COMPETITOR_ANALYSIS)

## Brand commitments

- **Visual canon (user-pinned):** Hosted surfaces match Sentry welcome / product chrome language — purple-black `#1F1633`, Rubik + IBM Plex Mono, gold CTA gradient, pink `#FD44B0` / blurple `#6A5FC1` accents — with Mutiny name/copy only (see `DESIGN.md`).
- Product name **Mutiny** is the hero brand signal on marketing surfaces.

## Terminology

Campaign, candidate, genome, trace, fitness, violation, minimize, regression, attestation, PolicyEvaluator, adapter, adapter layer, `mutiny init`, `mutiny run`.

## Open decisions

- Exact live Featherless model pin for demos (config, not product truth)
- Package publish name / PyPI story for `pip install mutiny-ai` (CLI command `mutiny`; bare `mutiny` on PyPI is taken)
- How Hosted UI attaches to a customer-local `mutiny run` vs the sample/reference harness

## Assumptions

- Audience is technical; CLI-first install is appropriate; Hosted is Operate+Persuade for lineage
- Primary CTA: install Mutiny into your agent project / start fuzzing
- Platform is CLI + optional web (Next.js) per PRD
