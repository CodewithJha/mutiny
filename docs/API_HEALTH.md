# Hosted API health

`GET /api/health` reports the API's SQLite check, campaign capacity, and mutation
configuration. It is public even when `MUTINY_API_TOKEN` protects other routes.
Hosted remains an optional observation surface for customer projects; a healthy
response does not mean Hosted can execute a customer's adapter.

## Observe a response

From the repository root, start the API using its supported entrypoint:

```bash
uv sync --group dev
uv run python -m mutiny_api --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -sS http://127.0.0.1:8000/api/health
```

The following response was observed with an empty temporary SQLite database and
no mutation credentials configured. Version, schema, model, and latency values
can differ between installations or requests.

```json
{
  "status": "ok",
  "api": true,
  "db": true,
  "model": "unconfigured:meta-llama/Meta-Llama-3.1-8B-Instruct",
  "version": "0.1.0",
  "mutator_mode": "template",
  "llm_configured": false,
  "db_latency_ms": 0.022,
  "schema_version": "11",
  "max_concurrent_campaigns": 1,
  "running_campaigns": 0,
  "demo_pin": "iris-demo-pin",
  "target_allowlist": ["in_process_demo"],
  "adapter_loading": "trusted_demo_only"
}
```

## Core fields

| Field | Meaning |
|---|---|
| `status` | `ok` when the SQLite ping succeeds and the running count is below the reported campaign limit; otherwise `degraded`. See the interpretation notes below. |
| `api` | `true` when this handler produces a response. It does not check the web UI, a customer's adapter, or external services. |
| `db` | Whether a `SELECT 1` query on the API's SQLite connection succeeded. This is not a disk-write or backup-integrity test. |
| `model` | Mutation model name from configuration. When unconfigured, the value is `unconfigured:` followed by the default mutation model name. It is not the customer's target-agent model or a model connectivity result. |
| `version` | Installed `mutiny-api` package version; falls back to `0.0.0+unreleased` if package metadata is unavailable. Other workspace packages may have different versions. |

## Operational fields

| Field | Meaning |
|---|---|
| `mutator_mode` | `featherless` when the mutation configuration is usable; otherwise `template`. The label is also used for an explicitly configured compatible endpoint. |
| `llm_configured` | Whether the mutation config loader found a key and accepted the numeric settings. No model request is made, so this does not validate credentials or service availability. |
| `db_latency_ms` | Elapsed time in milliseconds for the SQLite ping, rounded to three decimal places; `null` if the ping failed. Not whole-request latency. |
| `schema_version` | Schema version constant expected by this API build, currently `"11"`; not a separate live schema audit. |
| `max_concurrent_campaigns` | Reported Hosted execution limit, currently `1`. |
| `running_campaigns` | Number of persisted campaign rows whose status is `running`; not a count of worker threads or campaigns still marked `created`. |
| `demo_pin` | Legacy demo marker, currently `"iris-demo-pin"`. Its presence does not verify the contents of `config/demo_pin.json`. |
| `target_allowlist` | Hosted execution targets advertised by this API: currently only the bundled `in_process_demo` harness. |
| `adapter_loading` | `trusted_demo_only`: customer adapter loading is removed from Hosted. Customer execution stays in the Local CLI, with optional redacted ingest sync. |

## Interpreting health

- An unconfigured mutation model is a normal offline state: `llm_configured=false`
  and `mutator_mode=template` can accompany `status=ok`.
- A full campaign slot produces `status=degraded` even while `api` and `db` are
  `true`. A local fixture with one `running` row returned this state with HTTP
  **200**. Check the JSON `status` and counts as well as the HTTP status.
- The handler can report `db=false` after a failed ping, but database failures
  during its subsequent campaign query can fail the request altogether. Do not
  assume every database outage returns a structured `degraded` response; inspect
  server logs for non-200 responses or an unreachable API.
- The public route is still subject to enabled
  [Hosted rate limits](../SECURITY.md#hosted-rate-limits-p1-2). A `429` response
  is a rate-limit error, not a health payload; honor `Retry-After`.

See [Cold start](./COLD_START.md) for setup and
[Hosted ingestion](./HOSTED_INGESTION.md) for the Local CLI/Hosted boundary.
Implementation references: [`health()`](../apps/api/src/mutiny_api/app.py),
[`HealthResponse`](../apps/api/src/mutiny_api/schemas.py), and
the [mutation config loader](../packages/mutiny_core/src/mutiny_core/llm/config.py).
