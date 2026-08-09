#!/usr/bin/env bash
# One-command local Hosted stack (API :8000 + UI :3000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p data

export PYTHONPATH="${ROOT}/apps/api/src:${ROOT}/apps/demo_agent/src:${ROOT}/packages/mutiny_core/src${PYTHONPATH:+:$PYTHONPATH}"

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "${WEB_PID:-}" ]]; then kill "$WEB_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "→ API http://127.0.0.1:8000"
uv run uvicorn mutiny_api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

echo "→ waiting for /api/health"
for _ in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
    break
  fi
  sleep 0.25
done
curl -sf http://127.0.0.1:8000/api/health | head -c 200
echo

echo "→ UI  http://127.0.0.1:3000"
(cd "$ROOT/apps/web" && npm run dev) &
WEB_PID=$!

echo
echo "Mutiny Hosted is starting."
echo "  UI:  http://127.0.0.1:3000"
echo "  API: http://127.0.0.1:8000/api/health"
echo "  Docs: docs/COLD_START.md"
echo "Ctrl+C stops both."
wait
