# Planned integrations

This directory is a placeholder for future clients of Mutiny Core or the Hosted
API. It currently contains documentation only. No MCP server, published Skills,
or reusable regression-replay GitHub Action is shipped here.

- **Beta:** MCP server and coding-agent Skills — see the [Beta roadmap](../docs/ROADMAP.md#3-beta).
- **v1:** CI token and GitHub Action for regression replay — see the [v1 roadmap](../docs/ROADMAP.md#4-v1).

The existing [repository CI workflow](../.github/workflows/ci.yml) tests this
checkout; it is not a reusable GitHub Action for customer projects. Local
regression replay is available through `mutiny test`.

Future integrations must call the existing Core or API rather than duplicate
mutation, policy evaluation, fitness, or regression logic. Framework adapters
live under `packages/`, not in this directory. Read the
[architecture boundaries](../docs/ARCHITECTURE.md#future--secondary-integrations)
and [contributing guide](../CONTRIBUTING.md) before proposing an integration.
