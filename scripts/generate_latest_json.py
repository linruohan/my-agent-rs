#!/usr/bin/env python
"""Generate Tauri updater latest.json for GitHub Releases."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PLATFORMS = {
    "darwin-aarch64": "personal-assistant-agent_{ver}_aarch64.app.tar.gz",
    "darwin-x86_64": "personal-assistant-agent_{ver}_x64.app.tar.gz",
    "linux-x86_64": "personal-assistant-agent_{ver}_amd64.AppImage",
    "linux-aarch64": "personal-assistant-agent_{ver}_aarch64.AppImage",
    "windows-x86_64": "personal-assistant-agent_{ver}_x64-setup.exe",
    "windows-aarch64": "personal-assistant-agent_{ver}_arm64-setup.exe",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate latest.json for Tauri updater")
    parser.add_argument("--version", required=True, help="Release version e.g. 0.1.0")
    parser.add_argument(
        "--repo",
        default="YOUR_ORG/my-agent-rs",
        help="GitHub repo slug for download URLs",
    )
    parser.add_argument("--notes", default="", help="Release notes")
    parser.add_argument(
        "--signatures",
        default="",
        help="JSON file mapping platform key -> minisign signature content",
    )
    parser.add_argument("-o", "--output", default="latest.json")
    args = parser.parse_args()

    ver = args.version.lstrip("v")
    tag = args.version if args.version.startswith("v") else f"v{ver}"
    base = f"https://github.com/{args.repo}/releases/download/{tag}"

    sig_map: dict[str, str] = {}
    if args.signatures:
        sig_path = Path(args.signatures)
        if sig_path.is_file():
            sig_map = json.loads(sig_path.read_text(encoding="utf-8"))

    placeholder = "REPLACE_WITH_TAURI_SIGNER_SIGNATURE"
    platforms: dict[str, dict[str, str]] = {}
    for key, filename_tpl in DEFAULT_PLATFORMS.items():
        filename = filename_tpl.format(ver=ver)
        platforms[key] = {
            "signature": sig_map.get(key, placeholder),
            "url": f"{base}/{filename}",
        }

    manifest = {
        "version": ver,
        "notes": args.notes or f"Release {args.version}",
        "pub_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": platforms,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    missing = [k for k, v in platforms.items() if v["signature"] == placeholder]
    print(f"Wrote {args.output}")
    if missing:
        print(f"Missing signatures for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
