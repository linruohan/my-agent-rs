#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

MODE="${1:-web}"
PORT="${2:-8765}"

case "$MODE" in
  web)     exec "$SCRIPT_DIR/run-web.sh" "$PORT" ;;
  desktop) exec "$SCRIPT_DIR/run-desktop.sh" ;;
  sidecar) exec "$SCRIPT_DIR/run-sidecar.sh" "$PORT" ;;
  *)
    echo "Usage: $0 [web|desktop|sidecar] [port]" >&2
    exit 1
    ;;
esac
