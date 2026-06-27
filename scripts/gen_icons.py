#!/usr/bin/env python3
"""Generate minimal Tauri placeholder icons."""
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "src-tauri" / "icons"
ICONS.mkdir(parents=True, exist_ok=True)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    chunk = chunk_type + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, rgba=(59, 130, 246, 255)):
    r, g, b, a = rgba
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes([r, g, b, a]) * width
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", compressed)
    png += png_chunk(b"IEND", b"")
    path.write_bytes(png)


write_png(ICONS / "32x32.png", 32, 32)
write_png(ICONS / "128x128.png", 128, 128)
write_png(ICONS / "128x128@2x.png", 256, 256)
write_png(ICONS / "icon.ico", 32, 32)
write_png(ICONS / "icon.icns", 32, 32)
print("Icons generated.")
