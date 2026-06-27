#!/usr/bin/env python3
"""Build agent-api sidecar binary with PyInstaller in an isolated venv."""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
VENV_DIR = AGENT_DIR / ".venv"
OUT_DIR = ROOT / "src-tauri" / "binaries"
SPEC = AGENT_DIR / "agent-api.spec"


def get_target_triple() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "x86_64-pc-windows-msvc"
    if system == "darwin":
        return "aarch64-apple-darwin" if machine == "arm64" else "x86_64-apple-darwin"
    return "x86_64-unknown-linux-gnu"


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> Path:
    py = venv_python()
    if not py.exists():
        print(f"Creating venv at {VENV_DIR}...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    pip_cmds = [
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        [str(py), "-m", "pip", "install", "-e", f"{AGENT_DIR}[build]"],
        [str(py), "-m", "pip", "install", "pyinstaller>=6.0"],
    ]
    for cmd in pip_cmds:
        print(">", " ".join(cmd))
        subprocess.check_call(cmd)
    return py


def main():
    parser = argparse.ArgumentParser(description="Build agent-api sidecar")
    parser.add_argument("--skip-copy", action="store_true")
    parser.add_argument("--skip-venv", action="store_true", help="Use current Python instead of venv")
    args = parser.parse_args()

    py = sys.executable if args.skip_venv else ensure_venv()

    print(f"Building sidecar from {SPEC} using {py}...")
    subprocess.check_call(
        [
            str(py),
            "-m",
            "PyInstaller",
            str(SPEC),
            "--distpath",
            str(AGENT_DIR / "dist"),
            "--workpath",
            str(AGENT_DIR / "build"),
            "--noconfirm",
            "--clean",
        ],
        cwd=str(AGENT_DIR),
    )

    triple = get_target_triple()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    built_name = "agent-api.exe" if platform.system() == "Windows" else "agent-api"
    built = AGENT_DIR / "dist" / built_name
    if not built.exists():
        raise FileNotFoundError(f"Build output not found: {built}")

    dest = OUT_DIR / f"agent-api-{triple}{'.exe' if platform.system() == 'Windows' else ''}"
    if not args.skip_copy:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        shutil.copy2(built, tmp)
        tmp.replace(dest)
        print(f"Copied to {dest}")

    print("Sidecar build complete.")


if __name__ == "__main__":
    main()
