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

Load the project adapter + policy and start an evolutionary campaign. Optionally register with Hosted API when reachable.

| Flag | Default | Meaning |
|---|---|---|
| `--path PATH` | cwd | Project root |
| `--hosted-url HOSTED_URL` | from `mutiny.yaml` | Hosted API base URL override |
| `--no-hosted` | off | Skip Hosted registration; run locally only |
| `--attestation` | true | Confirm authorized testing |

```bash
mutiny run --no-hosted
mutiny run --path . --hosted-url http://127.0.0.1:8000
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
mutiny run --no-hosted
mutiny test
```

Sample offline harness: [`examples/openai_support_agent/`](../examples/openai_support_agent/).  
Install / Windows notes: [root README](../README.md#install) · [SUPPORT.md](../SUPPORT.md#windows).
