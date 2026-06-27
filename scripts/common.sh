#!/usr/bin/env bash
# Shared helpers for bash scripts
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

get_project_root() {
  if [[ ! -f "$ROOT/agent/main.py" ]]; then
    echo "Project root not found: $ROOT" >&2
    exit 1
  fi
  echo "$ROOT"
}

init_agent_env() {
  local root="$1"
  export AGENT_CONFIG_DIR="$root/agent/config"
  export AGENT_DATA_DIR="$root/data"
  mkdir -p "$AGENT_DATA_DIR"/{checkpoints,workspace,vectorstore}
}

assert_python() {
  if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "Python 3.11+ required" >&2
    exit 1
  fi
}

python_cmd() {
  if command -v python3 &>/dev/null; then echo python3; else echo python; fi
}

wait_sidecar_health() {
  local port="${1:-8765}"
  local timeout="${2:-45}"
  local url="http://127.0.0.1:${port}/health"
  for ((i=0; i<timeout*2; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

stop_sidecar() {
  local pid="$1"
  local port="${2:-8765}"
  curl -sf -X POST "http://127.0.0.1:${port}/shutdown" >/dev/null 2>&1 || true
  sleep 0.5
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
  fi
}
