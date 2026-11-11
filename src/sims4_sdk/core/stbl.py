"""Reader for STBL (string table) resources.

STBL resources (type ``0x220557DA``) map 32-bit FNV hashes to localized text.
They are stored inside DBPF packages, usually compressed with RefPack/zlib.

Binary layout (version 5)::

    char[4]  "STBL"
    uint16   version            (5)
    uint8    compressed         (unused by Maxis)
    uint64   string count
    uint16   reserved
    uint32   total string size (including a null byte per string)
    repeat string count times:
        uint32   key hash
        uint8    flags          (unused by Maxis)
        uint16   length         (UTF-8 byte length, null terminator excluded)
        byte[]   string data

The locale is encoded in the high byte of the resource instance ID
(``0x00`` = English, ``0x07`` = French, ...).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterator, Mapping, Optional

from ..exceptions import Sims4SDKError

__all__ = [
    "StringTable",
    "STBLError",
    "LOCALE_CODES",
    "locale_from_instance",
]

_HEADER = struct.Struct("<4sHBQHI")
_ENTRY = struct.Struct("<IBH")

#: Locale byte (high byte of a STBL instance ID) to language name.
LOCALE_CODES: dict[int, str] = {
    0x00: "ENG_US",
    0x01: "CHS_CN",
    0x02: "CHT_CN",
    0x03: "CSY_CZ",
    0x04: "DAN_DK",
    0x05: "NLD_NL",
    0x06: "FIN_FI",
    0x07: "FRA_FR",
    0x08: "DEU_DE",
    0x09: "ELL_GR",
    0x0A: "HUN_HU",
    0x0B: "ITA_IT",
    0x0C: "JPN_JP",
    0x0D: "KOR_KR",
    0x0E: "NOR_NO",
    0x0F: "POL_PL",
    0x10: "PRT_PT",
    0x11: "RUS_RU",
    0x12: "SPA_ES",
    0x13: "SWE_SE",
    0x14: "THA_TH",
    0x15: "TRK_TR",
    0x16: "BRZ_PT",
    0x17: "PLK_PL",
}


class STBLError(Sims4SDKError, ValueError):
    """Raised when an STBL resource is malformed."""


def locale_from_instance(instance: int) -> int:
    """Return the locale byte encoded in a STBL resource instance ID."""
    return (instance >> 56) & 0xFF


def locale_name(code: int) -> str:
    return LOCALE_CODES.get(code, f"0x{code:02X}")


@dataclass
class StringTable:
    """A parsed string table."""

    version: int = 5
    entries: dict[int, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes) -> "StringTable":
        """Parse a decompressed STBL resource."""
        if len(data) < _HEADER.size:
            raise STBLError(
                f"STBL is too small ({len(data)} bytes, need at least "
                f"{_HEADER.size})"
            )

        magic, version, _compressed, count, reserved, string_size = _HEADER.unpack_from(
            data, 0
        )
        if magic != b"STBL":
            raise STBLError(f"bad STBL magic {magic!r}")
        # ``compressed`` is documented but unused by Maxis and most mods; ignore it.
        if count > len(data):
            raise STBLError(f"implausible STBL entry count {count}")

        entries: dict[int, str] = {}
        pos = _HEADER.size
        total = len(data)

        for _ in range(count):
            if pos + _ENTRY.size > total:
                raise STBLError(
                    f"truncated STBL entry at offset {pos} "
                    f"({count - len(entries)} entries missing)"
                )
            key, flags, length = _ENTRY.unpack_from(data, pos)
            pos += _ENTRY.size
            end = pos + length
            if end > total:
                raise STBLError(
                    f"truncated STBL string for key 0x{key:08X} "
                    f"(wanted {length} bytes at offset {pos})"
                )
            raw = data[pos:end]
            pos = end
            # Maxis strings are not null terminated, but some mods include it.
            if raw.endswith(b"\x00"):
                raw = raw[:-1]
            entries[key] = raw.decode("utf-8", errors="replace")

        return cls(version=version, entries=entries)

    @classmethod
    def from_entries(cls, entries: Mapping[int, str], version: int = 5) -> "StringTable":
        return cls(version=version, entries=dict(entries))

    # ------------------------------------------------------------------
    # mapping interface
    # ------------------------------------------------------------------
    def get(self, key: int, default: Optional[str] = None) -> Optional[str]:
        return self.entries.get(key, default)

    def get_text(self, key: int, default: str = "") -> str:
        return self.entries.get(key, default)

    def __getitem__(self, key: int) -> str:
        return self.entries[key]

    def __contains__(self, key: int) -> bool:
        return key in self.entries

    def __iter__(self) -> Iterator[int]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def items(self):
        return self.entries.items()

    def keys(self):
        return self.entries.keys()

    def values(self):
        return self.entries.values()

    def merge(self, other: "StringTable", *, overwrite: bool = True) -> "StringTable":
        """Return a table combining this one with ``other``.

        Later tables (for example DLC overrides) win when ``overwrite`` is true.
        """
        merged = dict(self.entries)
        if overwrite:
            merged.update(other.entries)
        else:
            for key, value in other.entries.items():
                merged.setdefault(key, value)
        return StringTable(version=max(self.version, other.version), entries=merged)

    def update(self, other: "StringTable") -> None:
        self.entries.update(other.entries)

    def __repr__(self) -> str:
        return f"StringTable(version={self.version}, entries={len(self.entries)})"
