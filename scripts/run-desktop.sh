#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

ROOT="$(get_project_root)"
init_agent_env "$ROOT"

if ! command -v cargo &>/dev/null; then
  echo "Warning: Rust/cargo not found. Install from https://rustup.rs"
fi

echo "==> Starting Tauri desktop dev..."
cd "$ROOT"
npm run tauri dev
