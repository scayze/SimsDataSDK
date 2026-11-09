"""Shared test helpers and fixtures."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from sims4_sdk.paths import find_install_dir, find_user_dir


# ----------------------------------------------------------------------
# synthetic DBPF writer
# ----------------------------------------------------------------------
def build_package(
    entries: list[dict],
    *,
    index_flags: int = 0,
    constants: dict[int, int] | None = None,
) -> bytes:
    """Build a minimal but valid DBPF 2.1 package.

    ``entries`` items accept ``type``, ``group``, ``instance``, ``data`` and
    optionally ``compression`` (``"none"`` or ``"zlib"``).
    """
    constants = constants or {}
    entry_count = len(entries)
    constant_count = bin(index_flags & 0x0F).count("1")
    entry_size = 4 * (4 - constant_count) + 16
    index_size = 4 + 4 * constant_count + entry_size * entry_count
    data_start = 96 + index_size

    index = bytearray()
    index += struct.pack("<I", index_flags)
    for bit in (0x01, 0x02, 0x04, 0x08):
        if index_flags & bit:
            index += struct.pack("<I", constants.get(bit, 0))

    blobs: list[bytes] = []
    cursor = data_start
    for entry in entries:
        data: bytes = entry["data"]
        compression = entry.get("compression", "none")
        if compression == "zlib":
            stored = zlib.compress(data)
            stored_size = len(stored) | 0x80000000
            compression_id = 0x5A42
        else:
            stored = data
            stored_size = len(stored)
            compression_id = 0x0000

        for bit, value in (
            (0x01, entry["type"]),
            (0x02, entry["group"]),
            (0x04, entry["instance"] >> 32),
            (0x08, entry["instance"] & 0xFFFFFFFF),
        ):
            if not (index_flags & bit):
                index += struct.pack("<I", value)

        index += struct.pack(
            "<IIIHH",
            cursor,
            stored_size,
            len(data),
            compression_id,
            1,
        )
        blobs.append(stored)
        cursor += len(stored)

    header = bytearray(96)
    header[0:4] = b"DBPF"
    struct.pack_into("<I", header, 4, 2)
    struct.pack_into("<I", header, 8, 1)
    struct.pack_into("<I", header, 0x24, entry_count)
    struct.pack_into("<I", header, 0x2C, index_size)
    struct.pack_into("<I", header, 0x40, 96)
    return bytes(header) + bytes(index) + b"".join(blobs)


# ----------------------------------------------------------------------
# synthetic STBL writer
# ----------------------------------------------------------------------
def build_stbl(pairs: list[tuple[int, str]], *, version: int = 5) -> bytes:
    body = bytearray()
    for key, text in pairs:
        raw = text.encode("utf-8")
        body += struct.pack("<IBH", key, 0, len(raw))
        body += raw

    header = (
        b"STBL"
        + struct.pack("<H", version)
        + b"\x00"
        + struct.pack("<Q", len(pairs))
        + struct.pack("<H", 0)
        + struct.pack("<I", sum(len(text.encode("utf-8")) + 1 for _, text in pairs))
    )
    return header + bytes(body)


@pytest.fixture(scope="session")
def install_dir() -> Path:
    path = find_install_dir()
    if path is None:
        pytest.skip("no Sims 4 installation found")
    return path


@pytest.fixture(scope="session")
def user_dir() -> Path:
    path = find_user_dir()
    if path is None:
        pytest.skip("no Sims 4 user directory found")
    return path
