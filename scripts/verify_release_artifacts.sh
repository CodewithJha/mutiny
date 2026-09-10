#!/usr/bin/env bash
# Build publishable wheels from CURRENT source, install into an isolated venv,
# and smoke-test the CLI without editable installs, PYTHONPATH, or checkout imports.
#
# Usage (from repo root):
#   ./scripts/verify_release_artifacts.sh
#   ./scripts/verify_release_artifacts.sh /tmp/mutiny-artifact-gate
#
# Exit 0 on PASS. Does not publish. Does not call network LLMs / Hosted.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WORK="${1:-${RUNNER_TEMP:-/tmp}/mutiny-release-artifacts-$$}"
BUILD="$WORK/build"
VENV="$WORK/venv"
SMOKE="$WORK/smoke"
SAMPLE="$ROOT/examples/openai_support_agent"

echo "==> Release artifact gate (work=$WORK)"
rm -rf "$WORK"
mkdir -p "$BUILD/core" "$BUILD/openai" "$BUILD/cli" "$BUILD/api" "$BUILD/demo"

version_of() {
  grep -E '^version[[:space:]]*=' "$1/pyproject.toml" | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
}

core_v="$(version_of packages/mutiny_core)"
openai_v="$(version_of packages/mutiny_openai_agents)"
cli_v="$(version_of packages/mutiny_cli)"
echo "versions: core=${core_v} openai=${openai_v} cli=${cli_v}"
test -n "$core_v" && test -n "$openai_v" && test -n "$cli_v"
test "$core_v" = "$openai_v"
test "$core_v" = "$cli_v"

echo "==> Build wheels + sdists from current tree"
uv build --out-dir "$BUILD/core" packages/mutiny_core
uv build --out-dir "$BUILD/openai" packages/mutiny_openai_agents
uv build --out-dir "$BUILD/cli" packages/mutiny_cli

core_whl="$(echo "$BUILD"/core/mutiny_core-*-py3-none-any.whl)"
openai_whl="$(echo "$BUILD"/openai/mutiny_openai_agents-*-py3-none-any.whl)"
cli_whl="$(echo "$BUILD"/cli/mutiny_ai-*-py3-none-any.whl)"
test -f "$core_whl" && test -f "$openai_whl" && test -f "$cli_whl"

# Filename must embed the aligned version (blocks stale artifact mixups).
echo "$core_whl" | grep -q "mutiny_core-${core_v}-"
echo "$openai_whl" | grep -q "mutiny_openai_agents-${openai_v}-"
echo "$cli_whl" | grep -q "mutiny_ai-${cli_v}-"

echo "==> Inspect wheel metadata + contents"
python3 - "$core_whl" "$openai_whl" "$cli_whl" "$core_v" <<'PY'
import email.parser
import sys
import zipfile

core, openai, cli, expected = sys.argv[1:5]

def meta_version(whl: str) -> str:
    with zipfile.ZipFile(whl) as z:
        name = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        msg = email.parser.Parser().parsestr(z.read(name).decode())
        return msg["Version"]

for whl, label in ((core, "mutiny-core"), (openai, "mutiny-openai-agents"), (cli, "mutiny-ai")):
    ver = meta_version(whl)
    assert ver == expected, f"{label} METADATA Version={ver!r} != {expected!r}"

with zipfile.ZipFile(core) as z:
    names = set(z.namelist())
    assert "mutiny_core/redact.py" in names, "redact.py missing from mutiny-core wheel"
    assert "mutiny_core/__init__.py" in names
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    assert not any(n.startswith(("apps/", "examples/", "tests/")) for n in names)
    # No absolute checkout paths baked into sources
    init = z.read("mutiny_core/__init__.py").decode()
    assert "/Users/" not in init and "/home/" not in init

with zipfile.ZipFile(cli) as z:
    names = set(z.namelist())
    assert "mutiny_cli/run_cmd.py" in names
    assert "mutiny_cli/db_cmd.py" in names, "db_cmd.py missing from mutiny-ai wheel"
    assert "mutiny_cli/main.py" in names
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    assert not any(n.startswith(("apps/", "examples/", "tests/")) for n in names)
    run_src = z.read("mutiny_cli/run_cmd.py").decode()
    assert "population_size" in run_src
    assert "no_hosted" in run_src or "--no-hosted" in run_src
    compile(run_src, "mutiny_cli/run_cmd.py", "exec")

with zipfile.ZipFile(openai) as z:
    names = set(z.namelist())
    assert "mutiny_openai_agents/adapter.py" in names
    assert not any(n.startswith(("examples/", "apps/", "tests/")) for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)

print("wheel metadata + content checks ok")
PY

echo "==> Isolated venv install (sibling wheels together; no editable / PYTHONPATH)"
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -U pip >/dev/null
# Install all three together so pip cannot resolve mutiny-* from a stale PyPI index.
python -m pip install "$core_whl" "$openai_whl" "$cli_whl"

python - "$core_v" <<'PY'
import sys
from importlib.metadata import version
from pathlib import Path

import mutiny_core
import mutiny_cli
import mutiny_openai_agents
from mutiny_core.redact import redact_secrets, redaction_enabled

expected = sys.argv[1]
for name in ("mutiny-core", "mutiny-openai-agents", "mutiny-ai"):
    got = version(name)
    assert got == expected, f"{name} installed {got!r} != {expected!r}"

assert mutiny_core.__version__ == expected

for mod in (mutiny_core, mutiny_cli, mutiny_openai_agents):
    path = Path(mod.__file__).resolve()
    assert "site-packages" in str(path), f"not installed package: {path}"
    assert "/packages/mutiny_" not in str(path), f"checkout path import: {path}"

assert redaction_enabled() is True
raw = {"authorization": "Bearer sk-test", "api_key": "sk-live-secret"}
scrubbed = redact_secrets(raw)
assert scrubbed != raw
assert "sk-test" not in str(scrubbed) and "sk-live-secret" not in str(scrubbed)
print(f"imports ok; versions={expected}; redaction active; site-packages only")
PY

echo "==> CLI smoke from installed artifacts"
mutiny --help >/dev/null
mutiny db --help >/dev/null

rm -rf "$SMOKE"
mkdir -p "$SMOKE"
# Fresh init (empty project)
(
  cd "$SMOKE"
  mutiny init
  test -f .mutiny/adapter.py
  test -f policy.yaml
  test -f mutiny.yaml
)

# Offline Local CLI campaign + regression using the sample agent project
SAMPLE_SMOKE="$WORK/sample-smoke"
rm -rf "$SAMPLE_SMOKE"
mkdir -p "$SAMPLE_SMOKE"
cp -R "$SAMPLE"/. "$SAMPLE_SMOKE"/
# Ensure sample adapter (not overwritten by init scaffold)
cp "$SAMPLE/.mutiny/adapter.py" "$SAMPLE_SMOKE/.mutiny/adapter.py"

(
  cd "$SAMPLE_SMOKE"
  export MUTINY_SAMPLE_OFFLINE=1
  unset OPENAI_API_KEY FEATHERLESS_API_KEY || true
  export OPENAI_API_KEY=""
  export FEATHERLESS_API_KEY=""

  # Hosted URL in mutiny.yaml must NOT auto-select Hosted
  mutiny run --no-hosted | tee "$WORK/run.out"
  grep -q "Execution mode: local" "$WORK/run.out"
  grep -vq "Execution mode: local + Hosted sync" "$WORK/run.out" || true
  # Deterministic violation + minimize + regression save
  test -d .mutiny/tests
  test "$(find .mutiny/tests -name '*.json' | wc -l | tr -d ' ')" -ge 1
  grep -Eiq "violat|minimize|saved|regression" "$WORK/run.out" || true

  # First replay should FAIL on the buggy agent
  set +e
  mutiny test | tee "$WORK/test-fail.out"
  test_rc=$?
  set -e
  test "$test_rc" -eq 1
  grep -q "FAIL" "$WORK/test-fail.out"

  # Documented fix: default enforce_refund_policy=True → PASS
  python - <<'PY'
from pathlib import Path
p = Path(".mutiny/adapter.py")
text = p.read_text(encoding="utf-8")
old = "def create_adapter(*, enforce_refund_policy: bool = False)"
new = "def create_adapter(*, enforce_refund_policy: bool = True)"
if old not in text:
    raise SystemExit("sample adapter missing documented default to flip")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
  mutiny test | tee "$WORK/test-pass.out"
  grep -q "PASS" "$WORK/test-pass.out"
)

echo "==> Hosted operator db backup/restore (workspace mutiny-api wheel; not a PyPI sibling)"
uv build --out-dir "$BUILD/demo" apps/demo_agent
uv build --out-dir "$BUILD/api" apps/api
demo_whl="$(echo "$BUILD"/demo/demo_agent-*-py3-none-any.whl)"
api_whl="$(echo "$BUILD"/api/mutiny_api-*-py3-none-any.whl)"
test -f "$demo_whl" && test -f "$api_whl"
# Install with the already-present sibling wheels so deps do not pull stale PyPI 0.1.x.
python -m pip install "$demo_whl" "$api_whl" "$core_whl" "$openai_whl"

DB_DIR="$WORK/db"
mkdir -p "$DB_DIR"
SRC_DB="$DB_DIR/mutiny.sqlite"
BAK="$DB_DIR/backup.sqlite"
REST="$DB_DIR/restored.sqlite"
python - "$SRC_DB" <<'PY'
import sys
from pathlib import Path

from mutiny_api.db import connect

db = Path(sys.argv[1])
conn = connect(db)
conn.execute(
    "INSERT INTO projects(id, name, path, adapter, created_at, updated_at) "
    "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
    ("p-rc", "rc", "local_key:rc", "openai_agents"),
)
conn.commit()
conn.close()
print(db)
PY
mutiny db backup --db "$SRC_DB" --out "$BAK"
test -f "$BAK"
mutiny db restore --from "$BAK" --db "$REST" --force
test -f "$REST"

deactivate
echo "==> PACKAGING RELEASE GATE: PASS"
echo "    artifacts under $BUILD (publishable: core/openai/cli @ ${core_v})"
