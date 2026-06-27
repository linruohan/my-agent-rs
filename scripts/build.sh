#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

SKIP_TESTS=false
SKIP_SIDECAR=false
SKIP_TAURI=false
DEV_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --skip-tests) SKIP_TESTS=true ;;
    --skip-sidecar) SKIP_SIDECAR=true ;;
    --skip-tauri) SKIP_TAURI=true ;;
    --dev-only) DEV_ONLY=true ;;
  esac
done

ROOT="$(get_project_root)"
PY="$(python_cmd)"
init_agent_env "$ROOT"
cd "$ROOT"

echo "==> Build Personal Assistant Agent"

if [[ "$SKIP_TESTS" != true ]]; then
  echo "==> Running agent tests..."
  $PY -m pytest tests/agent -q
fi

echo "==> Building frontend..."
npm run build

if [[ "$DEV_ONLY" == true ]]; then
  echo "==> Dev build complete (dist/ ready)."
  exit 0
fi

if [[ "$SKIP_SIDECAR" != true ]]; then
  echo "==> Building Sidecar binary (PyInstaller)..."
  $PY "$ROOT/scripts/build_sidecar.py"
fi

if [[ "$SKIP_TAURI" != true ]] && command -v cargo &>/dev/null; then
  echo "==> Building Tauri desktop bundle..."
  npm run tauri build
elif [[ "$SKIP_TAURI" != true ]]; then
  echo "Warning: Skipping Tauri build (cargo not found)."
fi

echo "==> Build complete!"
