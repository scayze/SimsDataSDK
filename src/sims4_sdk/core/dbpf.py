"""Reader for The Sims 4 DBPF 2.x containers (``.package``, ``.world``, ``.save``).

A DBPF file is a flat archive identified by the ``DBPF`` magic.  It has a fixed
96-byte header followed by a resource index and resource data::

    header (96 bytes)
    ...
    resource data
    index (at ``index_offset``)
        uint32 flags
        optional constant fields (type/group/instance high/instance low)
        ``entry_count`` entries

The index uses a bitmask: a field whose bit is set is stored once, up front, and
is identical for every entry.  Save files for example store the group once, so
their entries are 28 bytes instead of the usual 32.  The reader handles both.

Each index entry contains ``(type, group, instance)`` plus the data offset, the
stored size, the decompressed size, and a compression ID.  The high bit of the
stored size marks a resource as compressed.  Three compression modes occur in
practice:

* ``0x0000`` — stored as-is,
* ``0x5A42`` — zlib (``ZB``),
* ``0xFFFF`` / ``0xFFFE`` / ``0xFFE0`` — EA RefPack/QFS.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, Optional

from . import refpack

__all__ = [
    "DBPF",
    "DBPFError",
    "DBPFHeader",
    "ResourceEntry",
    "ResourceKey",
    "COMPRESSION_NONE",
    "COMPRESSION_ZLIB",
    "COMPRESSION_REFPACK",
]

DBPF_MAGIC = b"DBPF"
DBPF_HEADER_SIZE = 96

COMPRESSION_NONE = 0x0000
COMPRESSION_ZLIB = 0x5A42
COMPRESSION_REFPACK = 0xFFFF
COMPRESSION_REFPACK_ALT = 0xFFFE
COMPRESSION_UNCOMPRESSED_ALT = 0xFFE0

#: High bit of the stored-size field indicating that the resource is compressed.
_COMPRESSED_FLAG = 0x80000000
_SIZE_MASK = 0x7FFFFFFF

# Index bitmask: which key fields are stored once for the whole table.
_CONST_TYPE = 0x01
_CONST_GROUP = 0x02
_CONST_INSTANCE_HIGH = 0x04
_CONST_INSTANCE_LOW = 0x08
_KNOWN_INDEX_FLAGS = _CONST_TYPE | _CONST_GROUP | _CONST_INSTANCE_HIGH | _CONST_INSTANCE_LOW


class DBPFError(ValueError):
    """Raised when a DBPF container cannot be parsed or decompressed."""


@dataclass(frozen=True, order=True)
class ResourceKey:
    """A resource identifier: ``type`` / ``group`` / ``instance``."""

    type_id: int
    group: int
    instance: int

    def __str__(self) -> str:
        return f"{self.type_id:08X}!{self.group:08X}!{self.instance:016X}"

    @classmethod
    def from_text(cls, text: str) -> "ResourceKey":
        """Parse ``"TTTTTTTT!GGGGGGGG!IIIIIIIIIIIIIIII"``."""
        parts = text.strip().split("!")
        if len(parts) != 3:
            raise ValueError(f"invalid resource key: {text!r}")
        return cls(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16))


@dataclass(frozen=True)
class ResourceEntry:
    """One resource in a package index."""

    key: ResourceKey
    offset: int
    size: int
    mem_size: int
    compression: int
    committed: bool = True
    compressed: bool = False

    @property
    def is_null(self) -> bool:
        """True for placeholder index entries that point at no data."""
        return self.offset == 0 or self.size == 0

    @property
    def stored_size(self) -> int:
        return self.size


@dataclass(frozen=True)
class DBPFHeader:
    magic: bytes
    major_version: int
    minor_version: int
    entry_count: int
    index_offset: int
    index_size: int
    file_size: int


class DBPF:
    """Read a DBPF 2.x container.

    The file is opened lazily for each resource read, so a :class:`DBPF` instance
    can be kept around cheaply and is safe to share between threads.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.header: DBPFHeader
        self.entries: list[ResourceEntry]
        self._index_flags = 0
        self.header, self.entries, self._index_flags = self._parse()

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def open(cls, path: str | Path) -> "DBPF":
        return cls(path)

    def _parse(self) -> tuple[DBPFHeader, list[ResourceEntry], int]:
        try:
            fp = open(self.path, "rb")
        except OSError as exc:
            raise DBPFError(f"cannot open {self.path}: {exc}") from exc

        with fp:
            data = fp.read(DBPF_HEADER_SIZE)
            if len(data) < DBPF_HEADER_SIZE:
                raise DBPFError(
                    f"{self.path.name}: file is too small for a DBPF header "
                    f"({len(data)} bytes)"
                )
            if data[:4] != DBPF_MAGIC:
                raise DBPFError(
                    f"{self.path.name}: bad magic {data[:4]!r} (expected b'DBPF')"
                )

            major, minor = struct.unpack_from("<II", data, 4)
            entry_count = struct.unpack_from("<I", data, 0x24)[0]
            index_size = struct.unpack_from("<I", data, 0x2C)[0]
            index_offset = struct.unpack_from("<I", data, 0x40)[0]

            fp.seek(0, 2)
            file_size = fp.tell()
            if index_offset + 4 > file_size:
                raise DBPFError(
                    f"{self.path.name}: index offset {index_offset} is past EOF"
                )

            fp.seek(index_offset)
            index_start = fp.tell()
            raw_flags = fp.read(4)
            if len(raw_flags) < 4:
                raise DBPFError(f"{self.path.name}: truncated index header")
            (index_flags,) = struct.unpack("<I", raw_flags)

            if index_flags & ~_KNOWN_INDEX_FLAGS:
                # No constant-field bitmask: this is a plain entry array.
                fp.seek(index_start)
                index_flags = 0
                entries = self._read_entries(fp, entry_count, index_flags)
            else:
                constants = self._read_constants(fp, index_flags)
                entries = self._read_entries(fp, entry_count, index_flags, constants)

        header = DBPFHeader(
            magic=data[:4],
            major_version=major,
            minor_version=minor,
            entry_count=entry_count,
            index_offset=index_offset,
            index_size=index_size,
            file_size=file_size,
        )
        return header, entries, index_flags

    @staticmethod
    def _read_constants(fp: BinaryIO, flags: int) -> dict[int, int]:
        constants: dict[int, int] = {}
        for bit, field in (
            (_CONST_TYPE, "type"),
            (_CONST_GROUP, "group"),
            (_CONST_INSTANCE_HIGH, "instance_high"),
            (_CONST_INSTANCE_LOW, "instance_low"),
        ):
            if flags & bit:
                raw = fp.read(4)
                if len(raw) < 4:
                    raise DBPFError("truncated constant index field")
                constants[bit] = struct.unpack("<I", raw)[0]
        return constants

    @staticmethod
    def _read_entries(
        fp: BinaryIO,
        count: int,
        flags: int,
        constants: Optional[dict[int, int]] = None,
    ) -> list[ResourceEntry]:
        constants = constants or {}
        entries: list[ResourceEntry] = []
        for _ in range(count):
            type_id = constants.get(_CONST_TYPE)
            if type_id is None:
                type_id = struct.unpack("<I", _read_exact(fp, 4))[0]
            group = constants.get(_CONST_GROUP)
            if group is None:
                group = struct.unpack("<I", _read_exact(fp, 4))[0]
            instance_high = constants.get(_CONST_INSTANCE_HIGH)
            if instance_high is None:
                instance_high = struct.unpack("<I", _read_exact(fp, 4))[0]
            instance_low = constants.get(_CONST_INSTANCE_LOW)
            if instance_low is None:
                instance_low = struct.unpack("<I", _read_exact(fp, 4))[0]

            offset = struct.unpack("<I", _read_exact(fp, 4))[0]
            stored_size = struct.unpack("<I", _read_exact(fp, 4))[0]
            mem_size = struct.unpack("<I", _read_exact(fp, 4))[0]
            compression, committed = struct.unpack("<HH", _read_exact(fp, 4))

            entries.append(
                ResourceEntry(
                    key=ResourceKey(
                        type_id=type_id,
                        group=group,
                        instance=(instance_high << 32) | instance_low,
                    ),
                    offset=offset,
                    size=stored_size & _SIZE_MASK,
                    mem_size=mem_size,
                    compression=compression,
                    committed=committed != 0,
                    compressed=bool(stored_size & _COMPRESSED_FLAG),
                )
            )
        return entries

    # ------------------------------------------------------------------
    # lookup
    # ------------------------------------------------------------------
    @property
    def index_flags(self) -> int:
        """The raw index bitmask (constant type/group/instance fields)."""
        return self._index_flags

    @property
    def resource_count(self) -> int:
        return len(self.entries)

    def iter_entries(
        self,
        type_id: Optional[int] = None,
        group: Optional[int] = None,
    ) -> Iterator[ResourceEntry]:
        """Yield entries, optionally filtered by type and/or group."""
        for entry in self.entries:
            if type_id is not None and entry.key.type_id != type_id:
                continue
            if group is not None and entry.key.group != group:
                continue
            yield entry

    def find_entry(self, key: ResourceKey) -> Optional[ResourceEntry]:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    def get_entry(
        self,
        type_id: int,
        group: int,
        instance: int,
    ) -> Optional[ResourceEntry]:
        return self.find_entry(ResourceKey(type_id, group, instance))

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def read_resource(self, entry: ResourceEntry | ResourceKey) -> bytes:
        """Read and decompress a resource."""
        if isinstance(entry, ResourceKey):
            found = self.find_entry(entry)
            if found is None:
                raise KeyError(f"resource not found: {entry}")
            entry = found

        if entry.is_null:
            return b""

        with open(self.path, "rb") as fp:
            fp.seek(entry.offset)
            raw = fp.read(entry.size)
        if len(raw) != entry.size:
            raise DBPFError(
                f"{self.path.name}: truncated resource {entry.key} "
                f"(wanted {entry.size} bytes, got {len(raw)})"
            )

        if not entry.compressed:
            return raw
        return self.decompress(entry.compression, raw, entry.mem_size)

    @staticmethod
    def decompress(compression: int, raw: bytes, mem_size: int = 0) -> bytes:
        """Decompress a resource body according to its compression ID."""
        if compression == COMPRESSION_ZLIB:
            return _zlib_or_fail(raw, mem_size)

        if compression in (
            COMPRESSION_REFPACK,
            COMPRESSION_REFPACK_ALT,
            COMPRESSION_UNCOMPRESSED_ALT,
        ):
            if refpack.is_refpack(raw):
                return refpack.decompress(raw)
            if compression == COMPRESSION_UNCOMPRESSED_ALT:
                return raw
            # Some shipped resources lie about the compression ID.
            try:
                return refpack.decompress(raw)
            except refpack.RefPackError:
                pass
            try:
                return _zlib_or_fail(raw, mem_size)
            except DBPFError:
                return raw

        if compression == COMPRESSION_NONE:
            return raw

        # Unknown compression ID: try the magic bytes before giving up.
        if refpack.is_refpack(raw):
            return refpack.decompress(raw)
        try:
            return _zlib_or_fail(raw, mem_size)
        except DBPFError:
            return raw

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------
    def __enter__(self) -> "DBPF":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def close(self) -> None:
        """Kept for API symmetry; no handle is held between reads."""

    def __repr__(self) -> str:
        return (
            f"DBPF({self.path.name!r}, entries={len(self.entries)}, "
            f"version={self.header.major_version}.{self.header.minor_version})"
        )


def _read_exact(fp: BinaryIO, count: int) -> bytes:
    data = fp.read(count)
    if len(data) != count:
        raise DBPFError(f"unexpected end of index (wanted {count} bytes)")
    return data


def _zlib_or_fail(raw: bytes, mem_size: int = 0) -> bytes:
    try:
        return zlib.decompress(raw)
    except zlib.error:
        # A handful of resources carry a 4-byte length prefix before the stream.
        try:
            return zlib.decompress(raw[4:])
        except zlib.error as exc:
            raise DBPFError(f"zlib decompression failed: {exc}") from exc
