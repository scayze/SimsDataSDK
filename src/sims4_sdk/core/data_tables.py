"""Decoder for EA's binary ``DATA`` table format.

The ``DATA`` format is the compiled companion to XML tuning.  It is used by
SimData resources (``0x545AC67A``) and by packed Combined Tuning blobs
(``0x62E94D38``) in DLC and delta packages.

Layout (little endian)::

    char[4]  "DATA"
    uint32   version            (0x100 or 0x101)
    int32    table header offset (relative to this field)
    int32    table count
    int32    schema offset       (relative to this field)
    int32    schema count
    uint32   unused              (version >= 0x101)

A *table* describes a homogeneous row array: its name, optional schema, row
size, row count, and where the rows begin.  A *schema* is a list of columns
(name, data type, byte offset within the row).  Values that reference other
data (strings, objects, variants) store a relative offset to a null-terminated
string or to another structure.

Rows are decoded lazily: :class:`TableRows` indexes into the original buffer on
demand instead of materialising every row up front.  A Combined Tuning blob can
contain more than five million rows, most of which are never read.

Reference: the format was documented by the S4TK project (MIT licensed) and is
also used by EA's official binary templates.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Iterator, Optional, Union

from ..exceptions import Sims4SDKError

__all__ = [
    "DataType",
    "DataTableError",
    "DataTables",
    "Schema",
    "SchemaColumn",
    "TableInfo",
    "TableRows",
]

RELOFFSET_NULL = -0x80000000

# Pre-compiled primitive readers: ``unpack_from`` directly on the buffer.
_U8 = struct.Struct("<B").unpack_from
_I8 = struct.Struct("<b").unpack_from
_U16 = struct.Struct("<H").unpack_from
_I16 = struct.Struct("<h").unpack_from
_U32 = struct.Struct("<I").unpack_from
_I32 = struct.Struct("<i").unpack_from
_U64 = struct.Struct("<Q").unpack_from
_I64 = struct.Struct("<q").unpack_from
_F32 = struct.Struct("<f").unpack_from


class DataTableError(Sims4SDKError, ValueError):
    """Raised when a DATA resource is malformed."""


class DataType(IntEnum):
    """Data types used by the DATA format."""

    Boolean = 0
    Character = 1
    Int8 = 2
    UInt8 = 3
    Int16 = 4
    UInt16 = 5
    Int32 = 6
    UInt32 = 7
    Int64 = 8
    UInt64 = 9
    Float = 10
    String = 11
    HashedString = 12
    Object = 13
    Vector = 14
    Float2 = 15
    Float3 = 16
    Float4 = 17
    TableSetReference = 18
    ResourceKey = 19
    LocalizationKey = 20
    Variant = 21
    Undefined = 22

    @staticmethod
    def alignment(data_type: int) -> int:
        if data_type in (0, 1, 2, 3):
            return 1
        if data_type in (4, 5):
            return 2
        if data_type in (6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21):
            return 4
        if data_type in (8, 9, 18, 19):
            return 8
        return 1


#: Serialised width of one value, used to compute row strides without walking
#: every row.  Matches the bytes :func:`_read_value` consumes.
_VALUE_SIZES = {
    0: 1,   # Boolean
    1: 1,   # Character
    2: 1,   # Int8
    3: 1,   # UInt8
    4: 2,   # Int16
    5: 2,   # UInt16
    6: 4,   # Int32
    7: 4,   # UInt32
    8: 8,   # Int64
    9: 8,   # UInt64
    10: 4,  # Float
    11: 4,  # String
    12: 8,  # HashedString
    13: 4,  # Object
    14: 8,  # Vector
    15: 8,  # Float2
    16: 12,  # Float3
    17: 16,  # Float4
    18: 8,  # TableSetReference
    19: 16,  # ResourceKey
    20: 4,  # LocalizationKey
    21: 8,  # Variant
    22: 0,  # Undefined
}


@dataclass
class TableInfo:
    name: Optional[str] = None
    name_hash: int = 0
    schema_offset_pos: int = 0
    schema_offset: int = 0
    data_type: int = 0
    row_size: int = 0
    row_offset_pos: int = 0
    row_offset: int = 0
    row_count: int = 0
    #: Index into :attr:`DataTables.schemas`, or ``-1`` for schemaless tables.
    schema_index: int = -1
    #: Absolute offset of the first row inside the DATA buffer.
    row_start: int = 0
    #: Distance between consecutive row starts.
    row_stride: int = 0

    @property
    def has_schema(self) -> bool:
        return self.schema_offset != RELOFFSET_NULL


@dataclass
class SchemaColumn:
    name: Optional[str] = None
    name_hash: int = 0
    data_type: int = 0
    flags: int = 0
    offset: int = 0
    schema_offset: int = 0


@dataclass
class Schema:
    name: Optional[str] = None
    name_hash: int = 0
    schema_hash: int = 0
    schema_size: int = 0
    column_offset_pos: int = 0
    column_offset: int = 0
    num_columns: int = 0
    columns: list[SchemaColumn] = field(default_factory=list)
    name_offset_pos: int = 0


class _Reader:
    """Small bounds-checked little-endian buffer reader for header parsing."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def tell(self) -> int:
        return self.pos

    def seek(self, pos: int) -> None:
        if pos < 0:
            raise DataTableError(f"negative seek position {pos}")
        self.pos = pos

    def _need(self, count: int) -> None:
        if self.pos + count > len(self.data):
            raise DataTableError(
                f"unexpected end of DATA (wanted {count} bytes at {self.pos})"
            )

    def uint8(self) -> int:
        self._need(1)
        value = self.data[self.pos]
        self.pos += 1
        return value

    def uint16(self) -> int:
        self._need(2)
        value = _U16(self.data, self.pos)[0]
        self.pos += 2
        return value

    def int32(self) -> int:
        self._need(4)
        value = _I32(self.data, self.pos)[0]
        self.pos += 4
        return value

    def uint32(self) -> int:
        self._need(4)
        value = _U32(self.data, self.pos)[0]
        self.pos += 4
        return value

    def cstring(self) -> str:
        end = self.data.find(b"\x00", self.pos)
        if end < 0:
            raise DataTableError(f"unterminated string at {self.pos}")
        value = self.data[self.pos : end].decode("utf-8", errors="replace")
        self.pos = end + 1
        return value

    def align(self, mask: int) -> None:
        self.pos += -self.pos & mask


class TableRows(Sequence):
    """Lazily decoded rows of one DATA table.

    Supports ``len()``, integer indexing and slicing.  Each access decodes just
    that row out of the backing buffer, so huge tables stay cheap.
    """

    __slots__ = ("_data", "_table", "_columns", "_start", "_stride", "_count")

    def __init__(self, data: bytes, table: TableInfo, columns: Sequence[SchemaColumn]):
        self._data = data
        self._table = table
        self._columns = tuple(
            (column.name, column.data_type, column.offset) for column in columns
        )
        self._start = table.row_start
        self._stride = table.row_stride
        self._count = table.row_count

    # ------------------------------------------------------------------
    # Sequence protocol
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: Union[int, slice]) -> Any:
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(self._count))]
        count = self._count
        if index < 0:
            index += count
        if index < 0 or index >= count:
            raise IndexError("row index out of range")
        return self._read(index)

    def __iter__(self) -> Iterator[Any]:
        data = self._data
        read = self._read
        for index in range(self._count):
            yield read(index)

    def __repr__(self) -> str:
        return f"TableRows({self._table.name!r}, rows={self._count})"

    @property
    def start(self) -> int:
        return self._start

    @property
    def stride(self) -> int:
        return self._stride

    def index_of(self, position: int) -> int:
        """Return the row index that a buffer position belongs to."""
        return (position - self._start) // self._stride

    def position_of(self, index: int) -> int:
        return self._start + index * self._stride

    # ------------------------------------------------------------------
    # decoding
    # ------------------------------------------------------------------
    def _read(self, index: int) -> Any:
        data = self._data
        base = self._start + index * self._stride
        columns = self._columns
        if not columns:
            return _read_value(data, base, self._table.data_type)
        row: dict[Optional[str], Any] = {}
        for name, data_type, offset in columns:
            row[name] = _read_value(data, base + offset, data_type)
        return row


@dataclass
class DataTables:
    """A parsed DATA resource."""

    version: int
    tables: list[TableInfo]
    schemas: list[Schema]
    rows: list[TableRows]
    data: bytes

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes) -> "DataTables":
        if len(data) < 4 or data[:4] != b"DATA":
            raise DataTableError(
                f"not a DATA resource (magic {data[:4]!r})"
            )

        try:
            reader = _Reader(data)
            reader.seek(4)
            version = reader.uint32()
            if version not in (0x100, 0x101):
                raise DataTableError(f"unknown DATA version 0x{version:X}")

            table_header_pos = reader.tell()
            table_header_offset = reader.int32()
            table_count = reader.int32()

            schema_pos = reader.tell()
            schema_offset = reader.int32()
            schema_count = reader.int32()

            if version >= 0x101:
                reader.uint32()  # unused

            # ----------------------------------------------------------
            # table headers
            # ----------------------------------------------------------
            reader.seek(table_header_pos + table_header_offset)
            tables: list[TableInfo] = []
            for _ in range(table_count):
                table = TableInfo()
                table.name_offset_pos = reader.tell()
                name_offset = reader.int32()
                table.name_hash = reader.uint32()
                if name_offset != RELOFFSET_NULL:
                    table.name = _string_at(reader, table.name_offset_pos + name_offset)
                table.schema_offset_pos = reader.tell()
                table.schema_offset = reader.int32()
                table.data_type = reader.uint32()
                table.row_size = reader.uint32()
                table.row_offset_pos = reader.tell()
                table.row_offset = reader.int32()
                table.row_count = reader.uint32()
                tables.append(table)

            row_data_start = reader.tell()

            # ----------------------------------------------------------
            # schemas
            # ----------------------------------------------------------
            reader.seek(schema_pos + schema_offset)
            schemas: list[Schema] = []
            for _ in range(schema_count):
                schema = Schema()
                schema.name_offset_pos = reader.tell()
                name_offset = reader.int32()
                schema.name_hash = reader.uint32()
                if name_offset != RELOFFSET_NULL:
                    schema.name = _string_at(reader, schema.name_offset_pos + name_offset)
                schema.schema_hash = reader.uint32()
                schema.schema_size = reader.uint32()
                schema.column_offset_pos = reader.tell()
                schema.column_offset = reader.int32()
                schema.num_columns = reader.uint32()
                schema_end = reader.tell()

                reader.seek(schema.column_offset_pos + schema.column_offset)
                for _column in range(schema.num_columns):
                    column = SchemaColumn()
                    column_name_pos = reader.tell()
                    column_name_offset = reader.int32()
                    column.name_hash = reader.uint32()
                    if column_name_offset != RELOFFSET_NULL:
                        column.name = _string_at(
                            reader, column_name_pos + column_name_offset
                        )
                    column.data_type = reader.uint16()
                    column.flags = reader.uint16()
                    column.offset = reader.uint32()
                    column.schema_offset = reader.int32()
                    schema.columns.append(column)

                schema.columns.sort(key=lambda column: column.offset)
                reader.seek(schema_end)
                schemas.append(schema)
        except struct.error as exc:  # truncated header
            raise DataTableError(f"truncated DATA resource: {exc}") from exc

        # --------------------------------------------------------------
        # row layout
        # --------------------------------------------------------------
        schema_offsets = {
            schema.name_offset_pos: index for index, schema in enumerate(schemas)
        }
        schema_by_size: dict[int, int] = {}
        for index, schema in enumerate(schemas):
            schema_by_size.setdefault(schema.schema_size, index)

        rows: list[TableRows] = []
        position = row_data_start
        for table in tables:
            position = (position + 15) & ~15
            table.row_start = position
            if table.has_schema:
                absolute_schema = table.schema_offset_pos + table.schema_offset
                schema_index = schema_offsets.get(absolute_schema)
                if schema_index is None:
                    schema_index = schema_by_size.get(table.row_size)
                if schema_index is None:
                    raise DataTableError(
                        f"table {table.name!r}: no schema at offset {absolute_schema}"
                    )
                schema = schemas[schema_index]
                table.schema_index = schema_index
                stride = schema.schema_size
                table.row_stride = stride
                rows.append(TableRows(data, table, schema.columns))
            else:
                stride = _VALUE_SIZES.get(table.data_type, 0)
                table.row_stride = stride
                rows.append(TableRows(data, table, ()))
            position += stride * table.row_count

        return cls(version=version, tables=tables, schemas=schemas, rows=rows, data=data)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def table_names(self) -> list[str]:
        return [table.name or f"<table {index}>" for index, table in enumerate(self.tables)]

    def table_index(self, name: str) -> int:
        for index, table in enumerate(self.tables):
            if table.name == name:
                return index
        raise KeyError(f"no DATA table named {name!r}")

    def table(self, name: str) -> tuple[TableInfo, TableRows]:
        index = self.table_index(name)
        return self.tables[index], self.rows[index]

    def read_string(self, ref: dict[str, Any]) -> Optional[str]:
        """Resolve a String/HashedString/Object reference to text."""
        offset = ref.get("mDataOffset")
        if offset is None or offset == RELOFFSET_NULL:
            return None
        return _string_at(_Reader(self.data), ref["startof_mDataOffset"] + offset)

    def describe(self) -> str:
        lines = [f"DATA version 0x{self.version:X}: {len(self.tables)} tables"]
        for index, table in enumerate(self.tables):
            columns = ""
            for schema in self.schemas:
                if schema.name_offset_pos == table.schema_offset_pos + table.schema_offset:
                    columns = ", ".join(
                        f"{column.name}:{DataType(column.data_type).name}"
                        for column in schema.columns
                    )
                    break
            lines.append(
                f"  [{index}] {table.name!r} rows={table.row_count} "
                f"row_size={table.row_size} columns=[{columns}]"
            )
        return "\n".join(lines)


def _string_at(reader: _Reader, offset: int) -> Optional[str]:
    saved = reader.tell()
    try:
        reader.seek(offset)
        return reader.cstring()
    finally:
        reader.seek(saved)


def _read_value(data: bytes, pos: int, data_type: int) -> Any:
    """Decode one value at ``pos`` (the caller knows the type and bounds)."""
    if data_type == 6:  # Int32
        return _I32(data, pos)[0]
    if data_type == 7:  # UInt32
        return _U32(data, pos)[0]

    if data_type == 11 or data_type == 13:  # String / Object
        return {"startof_mDataOffset": pos, "mDataOffset": _I32(data, pos)[0]}
    if data_type == 12:  # HashedString
        return {
            "startof_mDataOffset": pos,
            "mDataOffset": _I32(data, pos)[0],
            "mHash": _U32(data, pos + 4)[0],
        }
    if data_type == 21:  # Variant
        return {
            "startof_mDataOffset": pos,
            "mDataOffset": _I32(data, pos)[0],
            "mTypeHash": _U32(data, pos + 4)[0],
        }
    if data_type == 14:  # Vector
        return {
            "startof_mDataOffset": pos,
            "mDataOffset": _I32(data, pos)[0],
            "mCount": _U32(data, pos + 4)[0],
        }

    if data_type == 0:  # Boolean
        return bool(data[pos])
    if data_type == 3 or data_type == 2:  # UInt8 / Int8
        return data[pos]
    if data_type == 1:  # Character
        return data[pos : pos + 1].decode("utf-8", errors="replace")
    if data_type == 4:  # Int16
        return _I16(data, pos)[0]
    if data_type == 5:  # UInt16
        return _U16(data, pos)[0]
    if data_type == 8 or data_type == 9:  # Int64 / UInt64
        return _U64(data, pos)[0]
    if data_type == 10:  # Float
        return _F32(data, pos)[0]
    if data_type == 15:  # Float2
        return (_F32(data, pos)[0], _F32(data, pos + 4)[0])
    if data_type == 16:  # Float3
        return (_F32(data, pos)[0], _F32(data, pos + 4)[0], _F32(data, pos + 8)[0])
    if data_type == 17:  # Float4
        return (
            _F32(data, pos)[0],
            _F32(data, pos + 4)[0],
            _F32(data, pos + 8)[0],
            _F32(data, pos + 12)[0],
        )
    if data_type == 18:  # TableSetReference
        return _U64(data, pos)[0]
    if data_type == 19:  # ResourceKey
        return {
            "instance": _U64(data, pos)[0],
            "type": _U32(data, pos + 8)[0],
            "group": _U32(data, pos + 12)[0],
        }
    if data_type == 20:  # LocalizationKey
        return _U32(data, pos)[0]
    if data_type == 22:  # Undefined
        return None
    raise DataTableError(f"unknown column data type {data_type}")
