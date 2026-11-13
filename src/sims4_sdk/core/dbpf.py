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
from pathlib import Path
from typing import Iterator, NamedTuple, Optional

from ..exceptions import Sims4SDKError
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

#: Largest possible index entry (all four key fields stored inline).
_MAX_ENTRY_SIZE = 32
#: The index may begin with a 4-byte flag word plus four constant fields.
_INDEX_PREFIX = 20

_U32 = struct.Struct("<I").unpack_from


class DBPFError(Sims4SDKError, ValueError):
    """Raised when a DBPF container cannot be parsed or decompressed."""


class ResourceKey(NamedTuple):
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


class ResourceEntry(NamedTuple):
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


class DBPFHeader(NamedTuple):
    magic: bytes
    major_version: int
    minor_version: int
    entry_count: int
    index_offset: int
    index_size: int
    file_size: int


class _IndexView:
    """A package index that materialises entries on demand."""

    __slots__ = (
        "buffer",
        "position",
        "count",
        "step",
        "has_type",
        "has_group",
        "has_high",
        "has_low",
        "const_type",
        "const_group",
        "const_high",
        "const_low",
        "_unpack",
        "_entry",
    )

    def __init__(
        self,
        buffer: bytes,
        position: int,
        count: int,
        flags: int,
        constants: dict[int, int],
    ):
        fields = []
        if not flags & _CONST_TYPE:
            fields.append("I")
        if not flags & _CONST_GROUP:
            fields.append("I")
        if not flags & _CONST_INSTANCE_HIGH:
            fields.append("I")
        if not flags & _CONST_INSTANCE_LOW:
            fields.append("I")
        entry_struct = struct.Struct("<" + "".join(fields) + "IIIHH")
        step = entry_struct.size
        if position + step * count > len(buffer):
            raise DBPFError("unexpected end of index (truncated entry table)")

        self.buffer = buffer
        self.position = position
        self.count = count
        self.step = step
        self.has_type = not flags & _CONST_TYPE
        self.has_group = not flags & _CONST_GROUP
        self.has_high = not flags & _CONST_INSTANCE_HIGH
        self.has_low = not flags & _CONST_INSTANCE_LOW
        self.const_type = constants.get(_CONST_TYPE, 0)
        self.const_group = constants.get(_CONST_GROUP, 0)
        self.const_high = constants.get(_CONST_INSTANCE_HIGH, 0)
        self.const_low = constants.get(_CONST_INSTANCE_LOW, 0)
        self._unpack = _U32
        self._entry = entry_struct.unpack_from

    def type_at(self, position: int) -> int:
        if self.has_type:
            return self._unpack(self.buffer, position)[0]
        return self.const_type

    def entry_at(self, position: int) -> ResourceEntry:
        values = self._entry(self.buffer, position)
        cursor = 0
        if self.has_type:
            type_id = values[cursor]
            cursor += 1
        else:
            type_id = self.const_type
        if self.has_group:
            group = values[cursor]
            cursor += 1
        else:
            group = self.const_group
        if self.has_high:
            instance_high = values[cursor]
            cursor += 1
        else:
            instance_high = self.const_high
        if self.has_low:
            instance_low = values[cursor]
            cursor += 1
        else:
            instance_low = self.const_low

        stored_size = values[cursor + 1]
        return ResourceEntry(
            ResourceKey(type_id, group, (instance_high << 32) | instance_low),
            values[cursor],
            stored_size & _SIZE_MASK,
            values[cursor + 2],
            values[cursor + 3],
            values[cursor + 4] != 0,
            bool(stored_size & _COMPRESSED_FLAG),
        )

    def __iter__(self) -> Iterator[ResourceEntry]:
        entry_at = self.entry_at
        for position in range(
            self.position, self.position + self.step * self.count, self.step
        ):
            yield entry_at(position)

    def __len__(self) -> int:
        return self.count

    def iter_typed(self, type_ids, group) -> Iterator[ResourceEntry]:
        """Yield entries matching ``type_ids`` and/or ``group`` without building the rest."""
        if group is not None:
            if type_ids is None:
                for entry in self:
                    if entry.key.group == group:
                        yield entry
                return
            for entry in self.iter_typed(type_ids, None):
                if entry.key.group == group:
                    yield entry
            return

        buffer = self.buffer
        step = self.step
        entry_at = self.entry_at
        if type_ids is None:
            yield from self
        elif self.has_type:
            unpack = self._unpack
            for position in range(
                self.position, self.position + step * self.count, step
            ):
                if unpack(buffer, position)[0] not in type_ids:
                    continue
                yield entry_at(position)
        elif self.const_type in type_ids:
            yield from self


class DBPF:
    """Read a DBPF 2.x container.

    The file is opened lazily for each resource read, so a :class:`DBPF` instance
    can be kept around cheaply and is safe to share between threads.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.header: DBPFHeader
        self._index_flags = 0
        self.header, self._index_view = self._parse()
        self._entries: Optional[list[ResourceEntry]] = None

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def open(cls, path: str | Path) -> "DBPF":
        return cls(path)

    def _parse(self):
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

            # Read the whole index once; entry-wise reads dominated the scan.
            fp.seek(index_offset)
            available = file_size - index_offset
            wanted = min(available, index_size, _INDEX_PREFIX + entry_count * _MAX_ENTRY_SIZE)
            index_data = fp.read(wanted)

        if len(index_data) < 4:
            raise DBPFError(f"{self.path.name}: truncated index header")

        (index_flags,) = struct.unpack_from("<I", index_data, 0)
        position = 4
        constants: dict[int, int] = {}
        if index_flags & ~_KNOWN_INDEX_FLAGS:
            # No constant-field bitmask: this is a plain entry array.
            index_flags = 0
            position = 0
        else:
            for bit in (_CONST_TYPE, _CONST_GROUP, _CONST_INSTANCE_HIGH, _CONST_INSTANCE_LOW):
                if index_flags & bit:
                    if position + 4 > len(index_data):
                        raise DBPFError("truncated constant index field")
                    constants[bit] = struct.unpack_from("<I", index_data, position)[0]
                    position += 4

        self._index_flags = index_flags
        header = DBPFHeader(
            magic=data[:4],
            major_version=major,
            minor_version=minor,
            entry_count=entry_count,
            index_offset=index_offset,
            index_size=index_size,
            file_size=file_size,
        )
        return header, _IndexView(index_data, position, entry_count, index_flags, constants)

    @property
    def entries(self) -> list[ResourceEntry]:
        """Every index entry, materialised on first use."""
        cached = self._entries
        if cached is None:
            cached = list(self._index_view)
            self._entries = cached
        return cached

    @entries.setter
    def entries(self, value: list[ResourceEntry]) -> None:
        self._entries = value

    # ------------------------------------------------------------------
    # lookup
    # ------------------------------------------------------------------
    @property
    def index_flags(self) -> int:
        """The raw index bitmask (constant type/group/instance fields)."""
        return self._index_flags

    @property
    def resource_count(self) -> int:
        return self.header.entry_count

    def iter_entries(
        self,
        type_id: Optional[int] = None,
        group: Optional[int] = None,
    ) -> Iterator[ResourceEntry]:
        """Yield entries, optionally filtered by type and/or group.

        Filtering happens against the raw index, so entries that do not match
        are never materialised.
        """
        if type_id is None and group is None:
            yield from self.entries
            return
        type_ids = None if type_id is None else {type_id}
        yield from self._index_view.iter_typed(type_ids, group)

    def iter_entries_for_types(self, type_ids) -> Iterator[ResourceEntry]:
        """Yield every entry whose type is in ``type_ids``."""
        return self._index_view.iter_typed(set(type_ids), None)

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
        return self.read_entry(self.path, entry)

    @staticmethod
    def read_entry(path: str | Path, entry: ResourceEntry) -> bytes:
        """Read one resource using an index entry, without parsing the index.

        This is useful when the entry came from a previous index scan: it avoids
        reopening and re-parsing the whole package for every resource.
        """
        if entry.is_null:
            return b""

        path = Path(path)
        with open(path, "rb") as fp:
            fp.seek(entry.offset)
            raw = fp.read(entry.size)
        if len(raw) != entry.size:
            raise DBPFError(
                f"{path.name}: truncated resource {entry.key} "
                f"(wanted {entry.size} bytes, got {len(raw)})"
            )

        if not entry.compressed:
            return raw
        return DBPF.decompress(entry.compression, raw, entry.mem_size)

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
                return _check_size(refpack.decompress(raw), mem_size)
            if compression == COMPRESSION_UNCOMPRESSED_ALT:
                return raw
            # Some shipped resources lie about the compression ID.
            try:
                return _check_size(refpack.decompress(raw), mem_size)
            except refpack.RefPackError:
                pass
            try:
                return _zlib_or_fail(raw, mem_size)
            except DBPFError as exc:
                raise DBPFError("invalid RefPack or zlib resource") from exc

        if compression == COMPRESSION_NONE:
            return raw

        # Unknown compression ID: try the magic bytes before giving up.
        if refpack.is_refpack(raw):
            return _check_size(refpack.decompress(raw), mem_size)
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


def _zlib_or_fail(raw: bytes, mem_size: int = 0) -> bytes:
    try:
        result = zlib.decompress(raw)
    except zlib.error:
        # A handful of resources carry a 4-byte length prefix before the stream.
        try:
            result = zlib.decompress(raw[4:])
        except zlib.error as exc:
            raise DBPFError(f"zlib decompression failed: {exc}") from exc
    return _check_size(result, mem_size)


def _check_size(data: bytes, expected: int) -> bytes:
    if expected and len(data) != expected:
        raise DBPFError(f"decompressed {len(data)} bytes, expected {expected}")
    return data
