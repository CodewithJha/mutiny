# Hosted rate-limit field guide

Hosted uses in-process token buckets on `/api/*` requests. **Limits are per
process, not distributed or cluster-wide.** Workers/replicas have independent
buckets, and process restarts reset them. This is a single-tenant control-plane
guard, not a durable usage quota. Local CLI/Core campaign execution is unaffected;
HTTP uploads to Hosted are subject to the ingest limits.

Implementation: [rate_limit.py](../apps/api/src/mutiny_api/rate_limit.py) and the
HTTP middleware in [app.py](../apps/api/src/mutiny_api/app.py). Authentication and
observe-only boundaries are described in [SECURITY.md](../SECURITY.md).

## Configuration

Set these variables on the **API process** before startup. Configuration is read
when the app is created; restart the API to apply changes. Setting variables only
on the web process or in a customer's `mutiny.yaml` does not configure the API.

| Environment variable | Default | Meaning |
|---|---|---|
| `MUTINY_RATE_LIMIT_ENABLED` | Auth-dependent | Enabled when `MUTINY_API_TOKEN` is non-empty after trimming; otherwise disabled for local demos. Explicit `1`/`0` overrides this. |
| `MUTINY_RATE_LIMIT_HEALTH_RPM` | 1200 | Health-category refill rate, requests per minute. |
| `MUTINY_RATE_LIMIT_HEALTH_BURST` | 120 | Health bucket capacity, requests. |
| `MUTINY_RATE_LIMIT_NORMAL_RPM` | 600 | Normal-category refill rate, requests per minute. |
| `MUTINY_RATE_LIMIT_NORMAL_BURST` | 120 | Normal bucket capacity, requests. |
| `MUTINY_RATE_LIMIT_EXPENSIVE_RPM` | 60 | Expensive-category refill rate, requests per minute. |
| `MUTINY_RATE_LIMIT_EXPENSIVE_BURST` | 15 | Expensive bucket capacity, requests. |
| `MUTINY_RATE_LIMIT_INGEST_RPM` | 300 | Ingest-category refill rate, requests per minute. |
| `MUTINY_RATE_LIMIT_INGEST_BURST` | 60 | Ingest bucket capacity, requests. |
| `MUTINY_RATE_LIMIT_MAX_KEYS` | 4096 | Maximum number of identity/category buckets held in memory per process. |
| `MUTINY_RATE_LIMIT_IDLE_SECONDS` | 300 | Idle time before a bucket is eligible for cleanup, in seconds. |

Unset, empty, or whitespace-only settings use their defaults. The enable flag
also accepts `true`, `yes`, `on`, `enabled` and `false`, `no`, `off`, `disabled`
(case-insensitive). Unrecognized flag values fail app creation. RPM, burst, and
`MAX_KEYS` must be positive integers. `IDLE_SECONDS` is parsed as a positive
number and accepts fractional seconds. Non-positive values and unparsable
numbers raise a configuration error, even when limiting is disabled; zero does
not mean unlimited. Use `MUTINY_RATE_LIMIT_ENABLED=0` to disable explicitly.
Disabling limits does not disable authentication or the non-loopback token guard.

## Categories and token buckets

| Category | Requests |
|---|---|
| Health | `/api/health` and `/api/meta`. These are public, but still rate limited when the limiter is enabled. |
| Ingest | Paths starting with `/api/ingest/v1/`. Payload-size/redaction checks still apply separately. |
| Expensive | `POST /api/campaigns`, `/api/campaigns/{id}/start`, `/api/candidates/{id}/minimize`, `/api/candidates/{id}/regression`, and `/api/tests/run`. |
| Normal | Other `/api/*` requests, including list/poll requests and opening an SSE event stream. Streamed events are not additional HTTP requests. |

Each identity has a separate bucket for each category. A new bucket starts full
at `BURST`; each request consumes one token. Tokens refill continuously at
`RPM / 60` per second, up to the burst capacity. RPM is a refill rate, not a
fixed-minute request counter. For example, RPM 60 and burst 2 allow two immediate
requests, then refill one token per second. Exhausting normal traffic does not
consume health or ingest capacity.

Cleanup happens during requests, not on a background timer. Buckets idle longer
than `IDLE_SECONDS` are removed. At `MAX_KEYS`, the least recently used bucket is
evicted to make room. A later request for a removed key creates a fresh bucket;
these bounds control memory, not persistent per-user accounting.

## Identity and authentication order

- A valid configured Bearer token uses the shared `tenant` identity. All clients
  holding that single-tenant token share capacity within each category.
- Missing/invalid Bearer credentials, or requests when no token is configured,
  use `ip:<request.client.host>` (`ip:unknown` when unavailable). The limiter
  does not read `X-Forwarded-For`; anonymous clients behind a proxy can share
  a bucket when the ASGI client address is the proxy.
- Raw tokens are not bucket keys. Separate categories still apply to both
  authenticated and anonymous identities.

Request order is request context/ID, rate limiter, authentication dependency,
then handler. Protected requests with bad credentials return 401 while under
limit; exhausted requests return 429 before authentication, including requests
with a valid token. A 429 does not prove that credentials were accepted.
Health/meta remain public. Rate limits do not restore removed customer execution
or filesystem access.

## 429 and Retry-After

An exhausted bucket returns HTTP 429 with `error.code=rate_limit_exceeded` and
`Retry-After`. The rejected request does not reach the route handler. Example
response for the normal category (delay and request ID vary):

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 1
X-Request-Id: example-request-id

{"error":{"code":"rate_limit_exceeded","message":"rate limit exceeded for normal operations; retry after the indicated delay","status":429,"request_id":"example-request-id"}}
```

The server emits a **whole-second delay**, not an HTTP date. It computes the
missing tokens divided by the category refill rate, then rounds positive delays
up to at least one second. This estimates when the bucket can admit one request;
other clients sharing it may consume that capacity first.

Clients should wait at least the indicated delay before retrying, bound their
attempts/total wait, and avoid retry storms. Retry only safe/idempotent operations;
ingest retries must preserve stable campaign/event IDs and sanitized payloads.
Keep redaction enabled. A 401 or payload-validation error needs its own handling,
not an unbounded rate-limit retry loop.

A Hosted sync failure can leave a successful local campaign with CLI exit 3;
local results remain authoritative. See [Hosted ingestion](./HOSTED_INGESTION.md)
for the current CLI sync and pending-file recovery contract. This HTTP guide
does not imply every client automatically retries.

## Operator checks

`GET /api/meta` reports `safety.rate_limits` as `in_process` or `disabled` and
`safety.rate_limits_distributed` as `false`. It does not expose effective numeric
limits; inspect API process configuration for those. If health probes receive
429, check the health bucket rather than treating it as a health-response payload;
see the [health field guide](./API_HEALTH.md).

Behavioral coverage lives in [unit tests](../tests/unit/test_rate_limit.py) and
[HTTP integration tests](../tests/integration/test_api_hosted_rate_limit.py).
