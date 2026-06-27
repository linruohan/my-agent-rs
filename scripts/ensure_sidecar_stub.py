#!/usr/bin/env python3
"""Ensure Tauri externalBin sidecar placeholder exists for dev/cargo check."""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src-tauri" / "binaries"
STUB_SRC = ROOT / "scripts" / "stub_sidecar.rs"


def get_target_triple() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "x86_64-pc-windows-msvc"
    if system == "darwin":
        return "aarch64-apple-darwin" if machine == "arm64" else "x86_64-apple-darwin"
    return "x86_64-unknown-linux-gnu"


def dest_path() -> Path:
    triple = get_target_triple()
    ext = ".exe" if platform.system() == "Windows" else ""
    return OUT_DIR / f"agent-api-{triple}{ext}"


def main() -> int:
    dest = dest_path()
    if dest.exists():
        print(f"Sidecar binary already exists: {dest}")
        return 0

    if not shutil.which("rustc"):
        print("Warning: rustc not found; skip sidecar stub (Tauri build may fail).")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Building sidecar stub -> {dest}")
    subprocess.check_call(["rustc", str(STUB_SRC), "-O", "-o", str(dest)])
    print("Stub sidecar ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
