# Mutiny CLI

Console script from the **`mutiny-ai`** PyPI package (`pip install mutiny-ai`).  
Source of truth for flags: `mutiny --help` and `mutiny <cmd> --help`.

```text
usage: mutiny [-h] {init,run,test} ...

Mutiny — behavioral fuzz-testing engine for AI agents. Commands: init, run,
test.

positional arguments:
  {init,run,test}
    init           Scaffold .mutiny/adapter.py, policy.yaml, mutiny.yaml
    run            Load adapter + policy and start a campaign
    test           Replay project regressions under .mutiny/tests/
                   (PASS/FAIL/SKIPPED report)
```

---

## `mutiny init`

Scaffold `.mutiny/adapter.py`, `policy.yaml`, and `mutiny.yaml` in a project root.

| Flag | Default | Meaning |
|---|---|---|
| `--path PATH` | cwd | Project root |
| `--force` | off | Overwrite existing scaffold files |

```bash
mutiny init
mutiny init --path /path/to/agent --force
```

---

## `mutiny run`

Load the project adapter + policy and start an evolutionary campaign.
**Default execution mode is local** (Core + `.mutiny/adapter.py`). Hosted is
opt-in only.

| Flag | Default | Meaning |
|---|---|---|
| `--path PATH` | cwd | Project root |
| `--hosted` | off | Explicit opt-in: **local Core exec + redacted Hosted ingest sync** (ADR-019 / M-PR8C — does **not** execute the adapter on Hosted; see [HOSTED_INGESTION.md](./HOSTED_INGESTION.md)) |
| `--hosted-url HOSTED_URL` | from `mutiny.yaml` | Hosted API base URL (implies `--hosted` sync; overrides `mutiny.yaml`) |
| `--no-hosted` | off | Force local (default behavior; kept for compatibility; conflicts with `--hosted` / `--hosted-url`) |
| `--attestation` / `--no-attestation` | attestation on | Confirm authorized testing (`--no-attestation` fails closed) |

**Hosted sync (M-PR8C):** After local campaign completion, CLI POSTs to `/api/ingest/v1/*` with `schema_version=1` and `redaction.applied=true`. Bearer from `MUTINY_API_TOKEN` when set. Local success + sync failure → exit **3** (local result remains authoritative). Missing `api_url` with `--hosted` → exit 2. Config URL alone never selects Hosted.

**Precedence:** CLI flags decide mode. `hosted.api_url` in `mutiny.yaml` only
supplies the URL when Hosted is explicitly selected — it never auto-selects Hosted.

```bash
mutiny run
mutiny run --hosted
MUTINY_API_TOKEN=… mutiny run --hosted
mutiny run --path . --hosted-url http://127.0.0.1:8000
mutiny run --no-hosted   # same as default local
```

---

## `mutiny test`

Replay regressions under `.mutiny/tests/` and print a PASS / FAIL / SKIPPED report.

| Arg / flag | Default | Meaning |
|---|---|---|
| `regression_id` | (all) | Optional id or name to run one case |
| `--path PATH` | cwd | Project root |
| `--failed` | off | Re-run only cases that failed in the last `.mutiny/test-report.json` |
| `--json` | off | Print structured JSON report to stdout |
| `--no-report` | off | Do not write `.mutiny/test-report.json` |

```bash
mutiny test
mutiny test --failed
mutiny test some_regression_id --json
```

---

## Typical loop

```bash
pip install mutiny-ai
cd /path/to/your/agent
mutiny init
# edit .mutiny/adapter.py + policy.yaml
mutiny run
mutiny test
```

Sample offline harness: [`examples/openai_support_agent/`](../examples/openai_support_agent/).  
Install / Windows notes: [root README](../README.md#install) · [SUPPORT.md](../SUPPORT.md#windows).
