# Hosted Ingestion Contract (M-PR8A / M-PR8B / M-PR8C / M-PR8D)

| Field | Value |
|---|---|
| **Status** | **Complete (M-PR8A–E)** — contract + Hosted ingest API + CLI local-exec sync + Web observe copy + **production customer `exec_module` removed** |
| **Milestone** | M-PR8A–E (ADR-019 observe-only Hosted) |
| **Anchors** | ADR-019 (Option A observe-only), ADR-021 (Bearer auth), M-PR3 (redaction), M-PR1 (historical kill-switch; superseded by M-PR8E) |
| **Last updated** | 2026-09-09 |

This document defines the **CLI → Hosted ingestion contract**: how a completed (or streaming) Local CLI campaign/test becomes Hosted lineage without Hosted executing customer Python.

**Out of scope here:** upload endpoints, schema migrations, CLI/Hosted runtime changes, workers, retries, signing, object storage, multi-tenancy.

---

## 1. Purpose

Give Mutiny a smallest stable contract so that:

1. Customer `.mutiny/adapter.py` always executes on the **Local CLI** trust domain.
2. Hosted persists **sanitized** campaign metadata, events, evidence, regressions, and test-run results.
3. Existing Hosted concepts (`projects`, `campaigns`, `candidates`, `traces`, `events`, `regressions`, `test_runs`, SSE) are **reused**, not duplicated under a second “runs” ontology.
4. Local campaign success **never** depends on Hosted availability.
5. Future `mutiny run --hosted` means **local execute + sync**, not “execute adapter inside Hosted.”

---

## 2. Architecture diagram

### Retired (pre-M-PR8E — no longer reachable)

```text
Hosted API  ──(MUTINY_ALLOW_PROJECT_EXEC)──► load_adapter_factory
        │                                    exec_module(customer)
        ▼
CampaignSupervisor customer path → REMOVED (410 hosted_customer_execution_removed)
```

`MUTINY_ALLOW_PROJECT_EXEC` is ignored. Trusted `in_process_demo` may still run in-process without customer `project_path`.

### Current (ADR-019 / this contract — **Implemented** through M-PR8E)

```text
Local CLI (mutiny run / mutiny test)
        │
        │  customer adapter + Core campaign / replay
        │  policy evaluate → fitness → minimize (raw in-memory OK)
        │  redact_secrets  ←── REQUIRED before any upload bytes
        ▼
Authenticated Hosted ingestion (JSON over existing /api)
        │
        ▼
SQLite persistence (campaigns / candidates / traces / events /
                    regressions / test_runs)
        │
        ▼
Existing SSE + Web lineage UI
```

Hosted **observes**; it does not `exec_module` customer trees for Production Hosted.

**M-PR8C decision — end-of-run sync:** `mutiny run --hosted` finishes the local Core campaign first, then uploads open → batch → (regression) → complete. No mid-run event streaming in this milestone (simpler reliability; Hosted is never required for local correctness).

---

## 3. Trust boundary

| Zone | Trust | May contain | Must not |
|---|---|---|---|
| **Local CLI** | Trusted execution | Customer adapter, credentials, filesystem, raw traces in memory | Depend on Hosted for correctness |
| **Upload wire** | Authenticated data plane | Redacted JSON envelopes (`schema_version`, IDs, events, artifacts) | Raw unredacted secrets; executable blobs treated as code |
| **Hosted API/DB/UI** | Control + lineage | Parsed JSON as **data**; Bearer gate (ADR-021) | `exec_module` customer code; map uploaded paths to server FS; dynamic import from artifacts |

**Hard rule:** Uploaded content is **evidence data**, not executable content. Persistence uses JSON ↔ typed/validated models; never `pickle`, never `eval`, never import paths from payloads.

---

## 4. Run identity

Reuse existing Hosted IDs. Do **not** invent a parallel ID space named “run” unless unavoidable; in product language “run” ≡ **campaign** (fuzz) or **test_run** (replay).

| Entity | ID source | Notes |
|---|---|---|
| **Project** | `projects.id` (UUID) | CLI upserts/links by stable local key: prefer Hosted `project_id` if known; else create via ingest with `local_project_key` (hash of resolved project root + adapter name). Path strings are **metadata labels**, not server filesystem mounts. |
| **Campaign** (“run”) | `campaigns.id` (UUID, **CLI-generated**) | Client chooses ID before first upload → natural idempotency key. |
| **Generation** | `candidates.generation` (int) | Same as Core/Hosted today. |
| **Candidate** | `candidates.id` (UUID from Core genome/candidate) | Upsert by ID under campaign. |
| **Execution** | `ExecutionTrace.candidate_id` + `session_id` | Trace is 1:1 with candidate in Hosted SQLite today (`traces.candidate_id` PK). |
| **Event** | Client `event_id` (UUID) + server `events.id` (autoincrement) | Client ID for idempotency; server ID for SSE cursor (`after_id`). |
| **Regression** | `regressions.id` (UUID) | Same artifact `version: "1"` as Core `RegressionTest`. |
| **Test run** | `test_runs.id` (UUID, CLI-generated) | Observes local `mutiny test` result; Hosted does not replay. |

**Ownership (single-tenant):** One Hosted deployment + one shared `MUTINY_API_TOKEN` (ADR-021). Ambiguity control = unique primary keys + optional `project_id` on campaigns. **No multi-tenant ACLs in this contract.** Cross-run mixing is prevented by requiring `campaign_id` on every event/artifact and rejecting mismatches.

**Observable campaign lifecycle** (reuse existing statuses — do not invent a second state machine):

| Status | Meaning |
|---|---|
| `created` | Campaign row registered; no terminal result |
| `running` | CLI reported start / in progress |
| `violation` | Terminal: verified policy break found |
| `completed` | Terminal: finished without violation |
| `failed` | Terminal: CLI/campaign error |

Internal Core transitions (`candidate.executing`, per-turn adapter steps) need not all be uploaded.

---

## 5. Event model

Upload the **smallest useful observable set** — a subset of Core `EventType` (`mutiny_core.events`):

| Type | Upload? | Why |
|---|---|---|
| `campaign.started` | **Yes** | Opens live UI / SSE |
| `generation.started` | **Yes** | Progress |
| `candidate.created` | Optional | Graph detail; may batch with scored |
| `candidate.executing` | **No** (default) | High volume, low product value |
| `candidate.scored` | **Yes** (summary payload) | Fitness / hit counts without full trace |
| `violation.detected` | **Yes** | Primary signal |
| `minimization.started` | **Yes** | Lineage |
| `minimization.step` | **No** (default) | Noisy |
| `exploit.minimized` | **Yes** | Lineage |
| `regression.created` | **Yes** | Ties to regression artifact |
| `campaign.completed` | **Yes** | Terminal |
| `campaign.error` | **Yes** | Terminal failure |

**Payload rules:**

- Must include `campaign_id`.
- Candidate-scoped events include `candidate_id` and `generation` when known.
- Payloads are **already redacted** JSON objects (same shapes Hosted stores today).
- Do not embed full `ExecutionTrace` inside every event; attach traces as **artifacts**.

---

## 6. Artifact model

### Metadata (always)

- `schema_version` (ingestion envelope; see §12)
- `campaign_id`, optional `project_id` / `local_project_key`
- Campaign config subset: population, generations, seed, `stop_on_first_violation`, adapter/framework id, policy id/version/hash if available
- `mutiny_version`, `execution_mode: "local_cli"`
- Timestamps (`started_at`, `completed_at`), terminal `status`, metrics counts
- Attestation flag (boolean already required by CLI/Hosted)

### Evidence artifacts

| Kind | Body | Natural key |
|---|---|---|
| `candidate` | genome summary, fitness, status, policy hits (redacted) | `candidate_id` |
| `trace` | redacted `ExecutionTrace` JSON | `candidate_id` |
| `minimize_result` | turn counts, rule ids, still_reproduces | `candidate_id` |
| `regression` | Core `RegressionTest` JSON (`version: "1"`) | `regression_id` |
| `test_run` | PASS/FAIL, duration, rule ids, redacted evidence summary | `test_run_id` |

**Not uploaded by default:** raw adapter `TraceTurn.raw` blobs if still present after redaction helpers; CLI should strip or redact `raw` before upload. Genome message text may contain attack content (expected) but must pass through `redact_secrets`.

---

## 7. Redaction boundary

M-PR3 boundary extended to the wire:

```text
Local runtime (raw OK in memory)
        ↓
PolicyEvaluator / fitness / minimize
        ↓
redact_secrets(...)          ← contract gate
        ↓
ingestion HTTP body
        ↓
Hosted validate + persist     ← Hosted SHOULD re-apply redact_secrets (defense in depth)
        ↓
SSE / API / UI
```

**Contract requirements:**

1. CLI **must** call `mutiny_core.redact.redact_secrets` on every event payload and artifact JSON before upload.
2. Hosted **must not** be the first/only redactor for uploaded customer evidence.
3. Envelope field `redaction: { "applied": true, "marker": "[REDACTED]" }` is required on ingest batches so implementations fail closed if missing (Hosted rejects with `400 redaction_required`).
4. `MUTINY_DISABLE_SECRET_REDACTION=1` on the CLI **disables uploads** under this contract (local-only persistence still allowed). Hosted must not accept `redaction.applied: false` for Production Hosted.

---

## 8. Authentication

Reuse **ADR-021 / M-PR7** unchanged:

- `Authorization: Bearer <MUTINY_API_TOKEN>` when the Hosted server has the env set.
- Same public exceptions: `GET /api/health`, `GET /api/meta`.
- Ingest routes are **protected** (same as campaigns/SSE today).
- Auth does **not** enable customer `exec_module` (orthogonal to M-PR1 / ADR-019).

No new auth scheme, signing keys, or per-project tokens in M-PR8A.

---

## 9. Idempotency

| Upload | Idempotency key | Hosted behavior (**Planned**) |
|---|---|---|
| Campaign open | `campaign_id` | Create-or-return; conflicting config → `409 campaign_conflict` |
| Event | `event_id` (client UUID) scoped to `campaign_id` | Ignore duplicate; do not append twice |
| Candidate / trace | `candidate_id` | Upsert (same as `Repository.upsert_candidate` / `upsert_trace`) |
| Regression | `regression_id` | Create-or-return; body hash mismatch → `409` |
| Test run | `test_run_id` | Create-or-return |

Optional batch header: `Idempotency-Key: <uuid>` for whole HTTP requests (transport-level); entity keys above remain authoritative.

**Replay:** Re-uploading the same redacted batch after success is a no-op. Re-uploading a **different** body under the same ID is a conflict, not a silent overwrite of divergent evidence (except candidate/trace upserts, which are last-writer-wins for progressive scoring — documented exception matching today’s supervisor upserts).

---

## 10. Ordering

- Hosted does **not** require a total order across the network.
- Preferred CLI pattern: monotonic `seq` (uint) per `campaign_id` in the envelope; Hosted stores it for debug but **does not block** on gaps.
- SSE cursor remains server `events.id` (autoincrement) after persist — same as today.
- Missing intermediate events are allowed; terminal `status` + `campaign.completed` / `campaign.error` are authoritative for UI completion.
- Out-of-order events: persist if IDs valid; UI may show progress non-monotonically until terminal.
- Incomplete / interrupted CLI: campaign may stay `running` until a later `complete`/`failed` upload, or CLI uploads `failed` with `reason: interrupted` on best-effort shutdown.
- **Not** a distributed log / Kafka semantics.

---

## 11. Failure semantics

```text
Local campaign / test finishes
        ↓
local exit code & local artifacts (.mutiny/tests, reports) are authoritative
        ↓
Hosted upload fails / times out
        ↓
CLI still reports local success/failure as today
        ↓
warn on stderr; write .mutiny/hosted-pending/<campaign_id>.json (sanitized)
        ↓
retry later (manual or future `mutiny sync`) — **not** auto-retried in M-PR8C
```

**Rules:**

1. Hosted unavailability **must not** flip a successful local campaign to failure.
2. When `--hosted` sync is requested and Hosted config is invalid **before** execution (e.g. missing `api_url`), fail closed (config error exit 2) — same spirit as today’s explicit Hosted selection. Hosted reachability is **not** a prerequisite for local execution.
3. When sync fails **after** local success: warn on stderr and exit **`3`** (`SYNC_FAILED_EXIT`) so automation can distinguish sync failure from local campaign failure (`1`). Local failure still returns `1` even if sync also fails/succeeds.
4. No Hosted round-trip inside Core evaluation loops.
5. `MUTINY_DISABLE_SECRET_REDACTION=1` refuses Hosted upload (sync exit 3 after local success); local persistence still allowed.

---

## 12. Versioning

Ingestion envelope (JSON):

```json
{
  "schema_version": 1,
  "mutiny_version": "0.x.y",
  "execution_mode": "local_cli",
  "redaction": { "applied": true, "marker": "[REDACTED]" },
  "campaign_id": "…",
  "project_id": "…",
  "seq": 1,
  "events": [],
  "artifacts": []
}
```

- `schema_version` is an integer; Hosted rejects unsupported versions with `400 unsupported_ingest_schema`.
- Additive fields allowed in v1; breaking changes bump the integer.
- Artifact-internal versions (e.g. regression `version: "1"`) remain as today.
- Transport: **JSON over HTTPS/HTTP** to the existing FastAPI Hosted API — no gRPC/protobuf in this contract.

---

## 13. Size limits

Contract defaults (Hosted configurable via env in implementation; names reserved):

| Limit | Default | Env (reserved) |
|---|---|---|
| Max event payload | 64 KiB | `MUTINY_INGEST_MAX_EVENT_BYTES` |
| Max trace artifact | 1 MiB | `MUTINY_INGEST_MAX_TRACE_BYTES` |
| Max regression artifact | 256 KiB | `MUTINY_INGEST_MAX_REGRESSION_BYTES` |
| Max events per batch | 100 | `MUTINY_INGEST_MAX_EVENTS_PER_BATCH` |
| Max batch body | 2 MiB | `MUTINY_INGEST_MAX_BATCH_BYTES` |

**v1 behavior:** reject oversized items with `413 payload_too_large` — **no** chunking, compression pipeline, or object storage. CLI should omit verbose candidate events or truncate `raw` fields before retry.

---

## 14. Regression / test-run representation

### Lineage (unchanged product semantics)

```text
campaign → violation candidate → minimize → RegressionTest → mutiny test → PASS/FAIL
```

Hosted stores:

1. Campaign + candidate + redacted trace (evidence).
2. `regressions` row: `id`, `campaign_id`, `candidate_id`, optional display `path`, `artifact_json` (Core shape).
3. `test_runs` row: observes CLI replay — `status` PASS/FAIL, durations, rule ids, redacted evidence summary.

**Ownership without new columns (v1):** regressions remain linked via `campaign_id` → `campaigns.project_id` (same join Hosted list-by-project uses today). Adding `project_id` on `regressions` is **deferred** (called out in PRODUCTION_READINESS later work) unless implementation proves the join insufficient.

**Hosted does not execute** regression replay for CLI-originated test runs. Existing `POST /api/tests/run` supervisor path remains interim localhost/demo behavior until M-PR8 removes customer exec.

---

## 15. CLI behavior (**Implemented** — M-PR8C)

| Command | Behavior |
|---|---|
| `mutiny run` | Local execution only (M-PR2). No upload. |
| `mutiny run --hosted` / `--hosted-url` | **Local Core execution**, then **end-of-run** redacted ingest to Hosted. **Does not** mean “run adapter inside Hosted.” |
| `mutiny test` | Local replay only by default. |
| `mutiny test --hosted` | **Not implemented in M-PR8C** (payload helper exists; CLI flag deferred). |

**Semantics:**

```text
mutiny run              = local
mutiny run --hosted     = local + Hosted sync (observe-only ingest)
```

`hosted.api_url` in `mutiny.yaml` alone never activates sync (M-PR2). Auth header: `Authorization: Bearer` from `MUTINY_API_TOKEN` when set.

The Hosted supervisor create/start path remains for **trusted `in_process_demo` only**. Customer `openai_agents` + `project_path` create/start returns **`410 Gone`** / `hosted_customer_execution_removed` (M-PR8E). The CLI `--hosted` path uses ingest only.

---

## 16. Hosted API behavior (**Implemented** — M-PR8B)

Prefer **campaign-centric** routes over a parallel `/runs` resource. New write paths are additive; existing GET/SSE stay.

### Implemented ingest API

| Method | Path | Role |
|---|---|---|
| `POST` | `/api/ingest/v1/campaigns` | Open/upsert observe campaign (`campaign_id` client-supplied). **Does not** start `CampaignSupervisor` customer exec. |
| `POST` | `/api/ingest/v1/campaigns/{campaign_id}/batch` | Idempotent events + artifacts (`schema_version`, redaction gate, size limits). |
| `POST` | `/api/ingest/v1/campaigns/{campaign_id}/complete` | Set terminal status + metrics. |
| `POST` | `/api/ingest/v1/regressions` | Upsert regression artifact (links `campaign_id` / `candidate_id`). |
| `POST` | `/api/ingest/v1/test-runs` | Upsert observed test-run result. |

### Auth / validation / idempotency (M-PR8B)

- **Auth:** same M-PR7 Bearer gate (`MUTINY_API_TOKEN`); ingest routes are protected.
- **Envelope:** `schema_version` must be `1` (`400 unsupported_ingest_schema` otherwise).
- **Redaction:** `redaction.applied: true` required (`400 redaction_required`); Hosted re-applies `redact_secrets` before persist.
- **Project identity:** `project_id` or opaque `local_project_key` (stored as `projects.path = local_key:<key>` — never opened as FS).
- **Idempotency:** campaign / event (`event_id`) / regression / test_run natural IDs; duplicates are no-ops; divergent bodies → `409`.
- **Candidates/traces:** last-writer-wins upsert (same as supervisor).
- **Ordering:** best-effort; optional `seq` stored for debug; gaps/out-of-order accepted.
- **Size limits:** defaults from §13 (`413 payload_too_large`); env overrides reserved.
- **SSE:** ingested events publish through the existing `EventHub` after persist (same SSE protocol).

### Existing routes (read / live UI — reuse)

- `GET /api/campaigns`, `GET /api/campaigns/{id}`
- `GET /api/campaigns/{id}/candidates`, `GET /api/candidates/{id}`
- `GET /api/campaigns/{id}/events` (**SSE** — unchanged protocol)
- `GET /api/regressions`, `GET /api/tests/runs`, …

### Explicit non-goals for ingest

- Do not overload `POST /api/campaigns/{id}/start` to mean “execute customer project” for Production Hosted.
- Trusted `in_process_demo` may keep a Hosted-executed path separately labeled.
- Customer `project_path` create/start/minimize/regression/test execution on Hosted returns **`410 hosted_customer_execution_removed`** (M-PR8E).
- Web observe-only UX copy is **done (M-PR8D)** — Local CLI executes; Hosted observes; trusted `in_process_demo` remains labeled as demo.

Validation on ingest: schema_version, required IDs, known event types, artifact kinds, payload shape (Pydantic), size limits, duplicate IDs, `redaction.applied`, Bearer auth.

---

## 17. SSE relationship

```text
CLI ingest batch
    → Repository.append_event / upsert_*  (same tables)
    → EventHub publish (same as supervisor)
    → GET /api/campaigns/{id}/events SSE
    → Web UI
```

- **One** SSE protocol; no second event stream.
- Wire format stays `{id, campaign_id, ts, type, payload}` as persisted today.
- `ready` + ping + close-when-terminal behavior unchanged.
- Ingest should publish to the hub after successful persist so live UIs work for CLI-originated campaigns.

---

## 18. Security constraints

1. **Data not code:** JSON evidence only; no deserialization gadgets; no loading uploaded `path` as `project_path` for `exec_module`.
2. **Path fields** in projects/regressions are opaque labels / client display strings under observe-only ingest — never `resolve_project_root` for execution from ingest payloads.
3. **M-PR1 remains** until customer exec is fully removed from Production Hosted paths.
4. **Secrets:** redact-before-upload + Hosted re-redact; auth token never logged.
5. **Single-tenant:** token gates the whole DB; not a substitute for future multi-tenant isolation.
6. **Attestation:** ingest campaigns still carry attestation=true semantics for authorized-testing product rule.
7. **Integrity (v1):** Bearer auth + idempotent IDs + optional content hash on artifacts (`sha256` of redacted bytes) for conflict detection — **no** cryptographic request signing required unless a later ADR says otherwise.

---

## 19. Future implementation sequence

| Stage | Scope | Status |
|---|---|---|
| **M-PR8A** | This contract + doc consistency | **Done (docs)** |
| **M-PR8B** | Hosted ingest endpoints + persistence wiring + contract tests (no customer exec required) | **Done (server)** |
| **M-PR8C** | CLI local-exec + end-of-run sync for `--hosted`; pending-file on sync fail | **Done (CLI)** |
| **M-PR8D** | Web copy “run locally, observe here” (SSE already wired from ingest) | **Done (Web)** |
| **M-PR8E** | Remove/disable Production Hosted customer `project_path` `exec_module` path; keep `in_process_demo` | **Done** |
| **Later** | Optional `mutiny sync` / `mutiny test --hosted`; size-limit tuning; regression `project_id` column if join proves insufficient | Deferred |

Each stage ships behind tests. M-PR8E completes the ADR-019 Hosted execution boundary (customer Python never in shared API process).

---

## Compatibility checklist

Preserved by M-PR8E (customer Hosted exec retired; demo + ingest retained):

- Local `mutiny run` / `mutiny test`
- Deterministic `PolicyEvaluator`, minimize, regression semantics
- M-PR1–M-PR8D behavior (M-PR1 opt-in superseded — ALLOW flag ignored)
- ADR-020 (policy-general seeds), ADR-021 (Bearer), ADR-019 (observe-only)
- Trusted Hosted `in_process_demo` harness; CLI `--hosted` uses ingest only

### Current limitations (post M-PR8E)

- `mutiny test --hosted` not wired (payload builder only) — remaining CLI sync work / later
- Automatic retry / `mutiny sync` command deferred (pending JSON written on sync failure)
- Web cannot distinguish local-success + sync-failure from a missing Hosted row: sync failures do not fully ingest, so Hosted never claims those runs were received. A terminal `failed` status on an ingested `execution_mode=local_cli` campaign means the CLI reported campaign failure, not Hosted sync failure.
