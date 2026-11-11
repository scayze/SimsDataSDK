"""Read save and Tray JPEG artwork without an image-processing dependency.

Tray images use a 24-byte wrapper and an XOR-obfuscated payload. Maxis JPEGs
may contain an ALFA PNG (or ALFJ JPEG) alpha image in an APP segment. The
color JPEG and the embedded mask are returned separately; compositing them
into an RGBA image is left to an image library chosen by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..exceptions import Sims4SDKError
from ..export import Serializable

__all__ = ["Artwork", "ArtworkError", "decode_artwork", "read_tray_image"]

_TRAY_MARKER = bytes.fromhex("8efc24489b780e3c0200000000000000")
_TRAY_XOR = bytes.fromhex("4125e6cd47bab21a")
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


class ArtworkError(Sims4SDKError, ValueError):
    """An artwork container, JPEG, or alpha segment is malformed."""


@dataclass(frozen=True)
class Artwork(Serializable):
    """JPEG bytes and an optional embedded alpha image (PNG or JPEG)."""

    jpeg: bytes
    alpha_mask: Optional[bytes] = None
    alpha_format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


def decode_artwork(data: bytes) -> Artwork:
    """Parse one JPEG, including its optional Maxis ALFA/ALFJ alpha segment.

    Trailing bytes after the JPEG end marker are omitted. Invalid image headers
    raise :class:`ArtworkError`; JPEG pixel data is not decoded or validated.
    """
    if not data.startswith(b"\xff\xd8"):
        raise ArtworkError("artwork is not a JPEG")
    pos = 2
    in_scan = False
    alpha_parts: list[bytes] = []
    alpha_size: Optional[int] = None
    alpha_format = None
    width = height = None
    while pos < len(data):
        if in_scan:
            pos = data.find(b"\xff", pos)
            if pos < 0:
                break
        if data[pos] != 0xFF:
            raise ArtworkError(f"expected JPEG marker at offset {pos}")
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos == len(data):
            break
        marker = data[pos]
        pos += 1
        if in_scan and (marker == 0 or 0xD0 <= marker <= 0xD7):
            continue
        in_scan = False
        if marker == 0xD9:
            alpha = b"".join(alpha_parts) if alpha_size is not None else None
            if alpha_size is not None and len(alpha) != alpha_size:
                raise ArtworkError("alpha segment length mismatch")
            if alpha is not None:
                signature = _PNG_MAGIC if alpha_format == "png" else b"\xff\xd8"
                if not alpha.startswith(signature):
                    raise ArtworkError(f"invalid {alpha_format} alpha image")
            return Artwork(data[:pos], alpha, alpha_format, width, height)
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0, 0xD8) or pos + 2 > len(data):
            raise ArtworkError("invalid JPEG marker")
        length = int.from_bytes(data[pos:pos + 2], "big")
        end = pos + length
        if length < 2 or end > len(data):
            raise ArtworkError("truncated JPEG segment")
        payload = data[pos + 2:end]
        if 0xE0 <= marker <= 0xEF and payload[:4] in (b"ALFA", b"ALFJ"):
            if alpha_size is not None or len(payload) < 8:
                raise ArtworkError("duplicate or truncated alpha segment")
            alpha_size = int.from_bytes(payload[4:8], "big")
            alpha_parts.append(payload[8:])
            alpha_format = "png" if payload[:4] == b"ALFA" else "jpeg"
        elif 0xE0 <= marker <= 0xEF and payload[:4] == b"ALFX":
            if alpha_size is None:
                raise ArtworkError("alpha continuation without an alpha segment")
            alpha_parts.append(payload[4:])
        elif marker in _SOF:
            if len(payload) < 5:
                raise ArtworkError("truncated JPEG frame")
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
        pos = end
        if marker == 0xDA:
            in_scan = True
    raise ArtworkError("JPEG has no end marker")


def read_tray_image(path: str | Path) -> Artwork:
    """Read a Tray ``.hhi`` or ``.sgi`` image, including supported wrappers."""
    data = Path(path).read_bytes()
    if data.startswith(b"\xff\xd8"):
        return decode_artwork(data)
    if len(data) < 24 or data[8:24] != _TRAY_MARKER:
        raise ArtworkError("unsupported Tray image wrapper")
    length = int.from_bytes(data[:8], "little")
    if length != len(data) - 24:
        raise ArtworkError("Tray image wrapper length mismatch")
    payload = bytes(value ^ _TRAY_XOR[index % 8] for index, value in enumerate(data[24:]))
    return decode_artwork(payload)
