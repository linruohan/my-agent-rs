#!/usr/bin/env python
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


def write_ico(path: Path, size: int = 32, rgba=(59, 130, 246, 255)):
    """Write a minimal valid Windows .ico (required by tauri-winres)."""
    r, g, b, a = rgba
    row = bytes([b, g, r, a]) * size
    xor_rows = b"".join(row for _ in range(size))
    and_row = b"\x00" * ((size + 31) // 32 * 4)
    and_mask = and_row * size
    bmp_header = struct.pack(
        "<IIIHHIIIIII",
        40,
        size,
        size * 2,
        1,
        32,
        0,
        len(xor_rows) + len(and_mask),
        0,
        0,
        0,
        0,
    )
    image_data = bmp_header + xor_rows + and_mask
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image_data), 22)
    path.write_bytes(header + entry + image_data)


write_png(ICONS / "32x32.png", 32, 32)
write_png(ICONS / "128x128.png", 128, 128)
write_png(ICONS / "128x128@2x.png", 256, 256)
write_ico(ICONS / "icon.ico", 32)
write_png(ICONS / "icon.icns", 32, 32)
print("Icons generated.")
