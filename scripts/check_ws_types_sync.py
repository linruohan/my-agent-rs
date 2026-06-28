#!/usr/bin/env python3
"""Fail if src/types/wsEvents.generated.ts is out of sync with ws_protocol.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "types" / "wsEvents.generated.ts"
GENERATOR = ROOT / "scripts" / "generate_ws_types.py"


def main() -> int:
    if not TARGET.is_file():
        print(f"Missing {TARGET.relative_to(ROOT)} — run: npm run gen:ws-types")
        return 1

    before = TARGET.read_bytes()
    subprocess.run([sys.executable, str(GENERATOR)], check=True, cwd=ROOT)
    after = TARGET.read_bytes()

    if before != after:
        print(
            "wsEvents.generated.ts is out of sync with agent/src/api/ws_protocol.py.\n"
            "Run: npm run gen:ws-types"
        )
        return 1

    print("WS TypeScript types are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
