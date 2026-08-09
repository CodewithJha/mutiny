#!/usr/bin/env bash
# Publish Mutiny packages to PyPI in dependency order.
# Requires: uv, and UV_PUBLISH_TOKEN=pypi-... (or TWINE_PASSWORD with twine).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${UV_PUBLISH_TOKEN:-}" && -z "${TWINE_PASSWORD:-}" && -z "${PYPI_TOKEN:-}" ]]; then
  cat <<'EOF' >&2
Missing PyPI credentials.

Create a token: https://pypi.org/manage/account/token/
  - Account scope (first upload), or per-project after names exist
  - Copy the token (starts with pypi-)

Then either:

  export UV_PUBLISH_TOKEN='pypi-...'
  ./scripts/publish_pypi.sh

Or use Trusted Publishing (no local token):
  1. https://pypi.org/manage/account/publishing/
  2. Pending publisher ×3 for mutiny-core, mutiny-openai-agents, mutiny-ai
     Owner=CodewithJha  Repo=mutiny  Workflow=publish.yml  Environment=pypi
  3. Create GitHub Environment "pypi" on the repo
  4. Actions → Publish to PyPI → Run workflow

See docs/PUBLISHING.md
EOF
  exit 1
fi

TOKEN="${UV_PUBLISH_TOKEN:-${PYPI_TOKEN:-${TWINE_PASSWORD:-}}}"

publish_one() {
  local pkg="$1"
  local out="$2"
  echo "==> Building $pkg"
  rm -rf "$out"
  uv build --out-dir "$out" "$pkg"
  echo "==> Uploading $out"
  uv publish --token "$TOKEN" "$out"/*
}

publish_one packages/mutiny_core dist/publish-core
publish_one packages/mutiny_openai_agents dist/publish-openai
publish_one packages/mutiny_cli dist/publish-cli

echo "Done. Verify:"
echo "  pip install mutiny-ai && mutiny --help"
echo "  https://pypi.org/project/mutiny-ai/"
