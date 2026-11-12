"""Game image resources: tuning icons (DST/DDS, PNG).

Tuning ``icon`` fields are resource-key strings such as
``2f7d0004:00000000:09481da496b04a84``.  The type is almost always
``0x2F7D0004`` (PNG), but the pixel bytes are stored in the ``0x00B2D882``
(DST — shuffled DDS) resource with the same group/instance.  Icon lookup
therefore matches by ``(group, instance)`` across the known image types.

DST is EA's obfuscated DDS: the 128-byte DDS header is intact (with a
``DST1``/``DST5`` FourCC) and the block data after it is shuffled.  This
module unshuffles it back to standard ``DXT1``/``DXT5`` DDS using only the
standard library. Pillow converts the decoded image to PNG on request.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

from ..exceptions import Sims4SDKError
from ..export import Serializable
from .dbpf import ResourceKey

__all__ = [
    "ImageError",
    "GameImage",
    "parse_image_key",
    "parse_icon_key",
    "decode_image",
    "dst_to_dds",
    "dds_info",
]

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_DDS_MAGIC = b"DDS "
_DDS_HEADER_SIZE = 128


class ImageError(Sims4SDKError, ValueError):
    """Raised when an image resource cannot be parsed."""


@dataclass(frozen=True)
class GameImage(Serializable):
    """Decoded image container (DDS bytes or PNG bytes).

    ``data`` is directly usable: standard DDS (``DXT1``/``DXT5``/...) or PNG.
    Shuffled DST input is unshuffled on decode. Use :meth:`to_png` for PNG.
    """

    key: ResourceKey
    data: bytes
    format: str = "UNKNOWN"
    width: Optional[int] = None
    height: Optional[int] = None

    @property
    def is_png(self) -> bool:
        return self.format.upper() == "PNG"

    @property
    def is_dds(self) -> bool:
        return self.format.upper().startswith(("DXT", "DST", "DDS"))

    def to_png(self) -> bytes:
        """Decode the image and return PNG bytes, preserving transparency."""
        from PIL import Image

        try:
            with Image.open(BytesIO(self.data)) as image:
                result = BytesIO()
                image.save(result, format="PNG")
                return result.getvalue()
        except (OSError, ValueError, SyntaxError) as exc:
            raise ImageError(f"could not convert image {self.key} to PNG: {exc}") from exc

    def save(self, path: Union[str, Path]) -> Path:
        """Write ``data`` to ``path`` (adds ``.dds``/``.png`` when missing)."""
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".png" if self.is_png else ".dds")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.data)
        return target


def parse_image_key(text: Optional[str]) -> Optional[ResourceKey]:
    """Parse ``TTTTTTTT:GGGGGGGG:IIIIIIIIIIIIIIII`` (``0x`` prefixes optional)."""
    if not text:
        return None
    parts = text.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        return ResourceKey(
            type_id=int(parts[0], 16),
            group=int(parts[1], 16),
            instance=int(parts[2], 16),
        )
    except ValueError:
        return None


def parse_icon_key(text: Optional[str]) -> Optional[ResourceKey]:
    """Parse a tuning ``icon`` field into a :class:`ResourceKey`."""
    return parse_image_key(text)


def dds_info(data: bytes) -> tuple[Optional[int], Optional[int], str]:
    """Return ``(width, height, fourcc)`` from a DDS/DST header."""
    if len(data) < _DDS_HEADER_SIZE or not data.startswith(_DDS_MAGIC):
        raise ImageError("not a DDS/DST image")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    try:
        fourcc = data[84:88].decode("ascii")
    except UnicodeDecodeError:
        fourcc = ""
    # Sanity: dimensions are small UI icons up to 1024px; reject garbage.
    if not 0 < width <= 4096 or not 0 < height <= 4096:
        raise ImageError(f"implausible DDS dimensions {width}x{height}")
    return width, height, fourcc.strip("\x00 ").upper()


def dst_to_dds(data: bytes) -> bytes:
    """Unshuffle DST1/DST5 block data into standard DXT1/DXT5 DDS."""
    width, height, fourcc = dds_info(data)
    if fourcc in ("DXT1", "DXT5", "DXT3", "ATI1", "ATI2", "RGBA"):
        return data
    if fourcc not in ("DST1", "DST5"):
        raise ImageError(f"unsupported DDS FourCC {fourcc!r}")
    if len(data) <= _DDS_HEADER_SIZE:
        raise ImageError("DST image has no block data")
    body = data[_DDS_HEADER_SIZE:]
    size = len(body)
    header = bytearray(data[:_DDS_HEADER_SIZE])
    if fourcc == "DST1":
        if size % 8:
            raise ImageError("truncated DST1 block data")
        half = size >> 1
        count = half // 4
        out = bytearray(size)
        for i in range(count):
            out[i * 8:i * 8 + 4] = body[i * 4:i * 4 + 4]
            out[i * 8 + 4:i * 8 + 8] = body[half + i * 4:half + i * 4 + 4]
        header[84:88] = b"DXT1"
        return bytes(header) + bytes(out)
    # DST5: temp layout is [2-byte c0][4-byte c2][6-byte c1][4-byte c3]
    # each of length size/8, size/4, 3*size/8, size/4; emit 16-byte blocks.
    if size % 16:
        raise ImageError("truncated DST5 block data")
    b0 = 0
    b2 = size >> 3
    b1 = b2 + (size >> 2)
    b3 = b1 + ((6 * size) >> 4)
    count = (b2 - b0) // 2
    out = bytearray(size)
    pos = 0
    for i in range(count):
        out[pos:pos + 2] = body[b0:b0 + 2]
        pos += 2
        b0 += 2
        out[pos:pos + 6] = body[b1:b1 + 6]
        pos += 6
        b1 += 6
        out[pos:pos + 4] = body[b2:b2 + 4]
        pos += 4
        b2 += 4
        out[pos:pos + 4] = body[b3:b3 + 4]
        pos += 4
        b3 += 4
    header[84:88] = b"DXT5"
    return bytes(header) + bytes(out)


def decode_image(key: ResourceKey, data: bytes) -> GameImage:
    """Build a :class:`GameImage` from raw resource bytes."""
    if data.startswith(_PNG_MAGIC):
        width = height = None
        if len(data) >= 24 and data[12:16] == b"IHDR":
            width = struct.unpack_from(">I", data, 16)[0]
            height = struct.unpack_from(">I", data, 20)[0]
            if not 0 < width <= 8192 or not 0 < height <= 8192:
                width = height = None
        return GameImage(key=key, data=data, format="PNG", width=width, height=height)
    if data.startswith(_DDS_MAGIC):
        _, _, fourcc = dds_info(data)
        if fourcc in ("DST1", "DST5"):
            raw = dst_to_dds(data)
            width, height, fourcc = dds_info(raw)
            return GameImage(key=key, data=raw, format=fourcc or "DDS",
                             width=width, height=height)
        width, height, _ = dds_info(data)
        return GameImage(key=key, data=data, format=fourcc or "DDS",
                         width=width, height=height)
    raise ImageError(f"unsupported image payload for {key} ({len(data)} bytes)")
