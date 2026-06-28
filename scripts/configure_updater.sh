#!/usr/bin/env bash
# Patch tauri.conf.json updater section from environment variables.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/src-tauri/tauri.conf.json"

if [[ ! -f "$CONF" ]]; then
  echo "Config not found: $CONF" >&2
  exit 1
fi

if [[ -z "${TAURI_UPDATER_PUBKEY:-}" && -z "${TAURI_UPDATER_ENDPOINT:-}" && -z "${TAURI_UPDATER_ACTIVE:-}" ]]; then
  echo "No TAURI_UPDATER_* env vars set; skipping updater configure."
  exit 0
fi

python - "$CONF" <<'PY'
import json
import os
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

updater = data.setdefault("plugins", {}).setdefault("updater", {})

if pubkey := os.environ.get("TAURI_UPDATER_PUBKEY"):
    updater["pubkey"] = pubkey
    print("Set updater.pubkey")
if endpoint := os.environ.get("TAURI_UPDATER_ENDPOINT"):
    updater["endpoints"] = [endpoint]
    print(f"Set updater.endpoints -> {endpoint}")
if active := os.environ.get("TAURI_UPDATER_ACTIVE"):
    updater["active"] = active.lower() in ("1", "true", "yes")
    print(f"Set updater.active -> {updater['active']}")

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"Updated {path}")
PY
