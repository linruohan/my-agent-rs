#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

PORT="${1:-8765}"
HOST="${2:-127.0.0.1}"
ROOT="$(get_project_root)"
PY="$(python_cmd)"
init_agent_env "$ROOT"

echo "==> Starting Sidecar on ${HOST}:${PORT}..."
echo "    AGENT_DATA_DIR=$AGENT_DATA_DIR"

cleanup_stale_agent_api "$PORT"

cd "$ROOT/agent"
exec $PY main.py --host "$HOST" --port "$PORT"
