#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

SIDECAR_PORT="${1:-8765}"
ROOT="$(get_project_root)"
PY="$(python_cmd)"
init_agent_env "$ROOT"

LOG="$AGENT_DATA_DIR/sidecar.log"
echo "==> Starting Personal Assistant Agent (Web Dev)"

cd "$ROOT/agent"
$PY main.py --host 127.0.0.1 --port "$SIDECAR_PORT" >"$LOG" 2>&1 &
SIDECAR_PID=$!

cleanup() {
  echo "==> Stopping Sidecar..."
  stop_sidecar "$SIDECAR_PID" "$SIDECAR_PORT"
}
trap cleanup EXIT INT TERM

echo "==> Sidecar PID $SIDECAR_PID, log: $LOG"

if ! wait_sidecar_health "$SIDECAR_PORT"; then
  tail -20 "$LOG" 2>/dev/null || true
  echo "Sidecar failed to start on port $SIDECAR_PORT" >&2
  exit 1
fi

echo "==> Sidecar ready at http://127.0.0.1:${SIDECAR_PORT}"
export VITE_SIDECAR_PORT="$SIDECAR_PORT"

cd "$ROOT"
echo "==> Starting Vite dev server (http://localhost:1420)..."
npm run dev
