#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

ROOT="$(get_project_root)"
PY="$(python_cmd)"
cd "$ROOT"

echo "==> Setup Personal Assistant Agent"
assert_python

if ! command -v npm &>/dev/null; then
  echo "Node.js/npm required" >&2
  exit 1
fi

echo "==> Installing Python dependencies..."
cd "$ROOT/agent"
$PY -m pip install --upgrade pip -q
$PY -m pip install -e ".[dev]" -q
cd "$ROOT"

echo "==> Installing Node dependencies..."
npm install

if [[ ! -f "$ROOT/src-tauri/icons/32x32.png" ]]; then
  echo "==> Generating placeholder icons..."
  $PY "$ROOT/scripts/gen_icons.py"
fi

init_agent_env "$ROOT"

echo "==> Ensuring Sidecar stub for Tauri dev..."
$PY "$ROOT/scripts/ensure_sidecar_stub.py"

echo "==> Setup complete."
echo ""
echo "Next steps:"
echo "  Web dev:     ./scripts/run-web.sh"
echo "  Desktop dev: ./scripts/run-desktop.sh"
echo "  Full build:  ./scripts/build.sh"
