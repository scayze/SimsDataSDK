"""Decompressor for EA's RefPack/QFS compression.

RefPack is the "proprietary" compression flagged by DBPF compression type
``0xFFFF`` (and ``0xFFFE``).  Sims 4 uses it for large resources such as STBL
string tables and Combined Tuning blobs.

The stream starts with a two byte magic (``10 FB`` or ``50 FB``, little-endian
``0xFB10`` / ``0xFB50``) followed by the decompressed size:

* if the first magic byte has bit ``0x80`` set, the size is a 4-byte big-endian
  integer;
* otherwise the size is a 3-byte big-endian integer.

The remainder is a stream of variable-length control codes:

===========  ===============================================================
Control      Meaning
===========  ===============================================================
``0x00-7F``  2-byte code: short back-reference followed by literals
``0x80-BF``  3-byte code: medium back-reference followed by literals
``0xC0-DF``  4-byte code: long back-reference followed by literals
``0xE0-FB``  1-byte code: literal run
``0xFC-FF``  stop code, optionally followed by 0-3 trailing literals
===========  ===============================================================

The implementation is defensive: corrupt or truncated streams raise
:class:`RefPackError` instead of returning silently wrong data.
"""

from __future__ import annotations

import struct

from ..exceptions import Sims4SDKError

__all__ = ["RefPackError", "is_refpack", "decompress"]

# First magic byte values observed in EA games.
_MAGIC_FIRST_BYTES = (0x10, 0x50, 0x90, 0xD0)


class RefPackError(Sims4SDKError, ValueError):
    """Raised when a RefPack stream is malformed or truncated."""


def is_refpack(data: bytes) -> bool:
    """Return ``True`` when ``data`` looks like a RefPack stream."""
    if len(data) < 2:
        return False
    if data[0] in _MAGIC_FIRST_BYTES and data[1] == 0xFB:
        return True
    # Some wrappers keep a 4-byte size prefix before the magic.
    if len(data) >= 6 and data[4] in _MAGIC_FIRST_BYTES and data[5] == 0xFB:
        return True
    return False


def _find_stream_start(data: bytes) -> int:
    if len(data) >= 2 and data[0] in _MAGIC_FIRST_BYTES and data[1] == 0xFB:
        return 0
    if len(data) >= 6 and data[4] in _MAGIC_FIRST_BYTES and data[5] == 0xFB:
        return 4
    raise RefPackError("missing RefPack magic (expected 0x10FB or 0x50FB)")


def _read_size(data: bytes, start: int) -> tuple[int, int]:
    """Return ``(decompressed_size, position_after_header)``."""
    flags = data[start]
    pos = start + 2
    if flags & 0x80:
        if pos + 4 > len(data):
            raise RefPackError("truncated 4-byte RefPack size")
        (size,) = struct.unpack_from(">I", data, pos)
        return size, pos + 4
    if pos + 3 > len(data):
        raise RefPackError("truncated 3-byte RefPack size")
    size = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
    return size, pos + 3


def decompress(data: bytes) -> bytes:
    """Decompress a RefPack/QFS stream.

    Raises:
        RefPackError: if the stream is malformed or truncated.
    """
    start = _find_stream_start(data)
    expected_size, pos = _read_size(data, start)

    out = bytearray()
    total = len(data)

    while pos < total:
        control = data[pos]

        if control <= 0x7F:
            # Short back-reference + literals (2-byte code).
            if pos + 1 >= total:
                raise RefPackError("truncated 2-byte RefPack code")
            b1 = data[pos + 1]
            literal_count = control & 0x03
            copy_length = ((control & 0x1C) >> 2) + 3
            copy_offset = ((control & 0x60) << 3) + b1 + 1
            pos += 2
            _append_literals(out, data, pos, literal_count)
            pos += literal_count
            _copy(out, copy_offset, copy_length)

        elif control <= 0xBF:
            # Medium back-reference + literals (3-byte code).
            if pos + 2 >= total:
                raise RefPackError("truncated 3-byte RefPack code")
            b1 = data[pos + 1]
            b2 = data[pos + 2]
            literal_count = (b1 >> 6) & 0x03
            copy_length = (control & 0x3F) + 4
            copy_offset = ((b1 & 0x3F) << 8) + b2 + 1
            pos += 3
            _append_literals(out, data, pos, literal_count)
            pos += literal_count
            _copy(out, copy_offset, copy_length)

        elif control <= 0xDF:
            # Long back-reference + literals (4-byte code).
            if pos + 3 >= total:
                raise RefPackError("truncated 4-byte RefPack code")
            b1 = data[pos + 1]
            b2 = data[pos + 2]
            b3 = data[pos + 3]
            literal_count = control & 0x03
            copy_length = ((control & 0x0C) << 6) + b3 + 5
            copy_offset = ((control & 0x10) << 12) + (b1 << 8) + b2 + 1
            pos += 4
            _append_literals(out, data, pos, literal_count)
            pos += literal_count
            _copy(out, copy_offset, copy_length)

        elif control <= 0xFB:
            # Literal run (1-byte code).
            literal_count = ((control & 0x1F) << 2) + 4
            pos += 1
            _append_literals(out, data, pos, literal_count)
            pos += literal_count

        else:
            # Stop code; 0-3 trailing literals.
            literal_count = control & 0x03
            pos += 1
            _append_literals(out, data, pos, literal_count)
            pos += literal_count
            break

    if len(out) < expected_size:
        raise RefPackError(
            f"decompressed {len(out)} bytes, header promised {expected_size}"
        )
    return bytes(out[:expected_size])


def _append_literals(out: bytearray, data: bytes, pos: int, count: int) -> None:
    if count == 0:
        return
    end = pos + count
    if end > len(data):
        raise RefPackError("truncated literal run")
    out.extend(data[pos:end])


def _copy(out: bytearray, offset: int, length: int) -> None:
    if offset <= 0 or offset > len(out):
        raise RefPackError(
            f"invalid back-reference offset {offset} (output has {len(out)} bytes)"
        )
    source = len(out) - offset
    if offset >= length:
        out.extend(out[source : source + length])
        return
    # Overlapping copies are legal (LZ77 run-length): the copied window repeats
    # with a period of ``offset``, so build it once instead of byte by byte.
    pattern = out[source:]
    repeats = -(-length // offset)
    out.extend((pattern * repeats)[:length])
