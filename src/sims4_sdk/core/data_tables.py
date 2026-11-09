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

Reference: the format was documented by the S4TK project (MIT licensed) and is
also used by EA's official binary templates.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

__all__ = [
    "DataType",
    "DataTableError",
    "DataTables",
    "Schema",
    "SchemaColumn",
    "TableInfo",
]

RELOFFSET_NULL = -0x80000000


class DataTableError(ValueError):
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
    """Small bounds-checked little-endian buffer reader."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def tell(self) -> int:
        return self.pos

    def seek(self, pos: int) -> None:
        if pos < 0:
            raise DataTableError(f"negative seek position {pos}")
        self.pos = pos

    def _take(self, count: int) -> bytes:
        end = self.pos + count
        if end > len(self.data):
            raise DataTableError(
                f"unexpected end of DATA (wanted {count} bytes at {self.pos})"
            )
        chunk = self.data[self.pos:end]
        self.pos = end
        return chunk

    def uint8(self) -> int:
        return self._take(1)[0]

    def int16(self) -> int:
        return struct.unpack("<h", self._take(2))[0]

    def uint16(self) -> int:
        return struct.unpack("<H", self._take(2))[0]

    def int32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def uint32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def uint64(self) -> int:
        return struct.unpack("<Q", self._take(8))[0]

    def float32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def chars(self, count: int) -> str:
        return self._take(count).decode("utf-8", errors="replace")

    def cstring(self) -> str:
        end = self.data.find(b"\x00", self.pos)
        if end < 0:
            raise DataTableError(f"unterminated string at {self.pos}")
        value = self.data[self.pos:end].decode("utf-8", errors="replace")
        self.pos = end + 1
        return value

    def align(self, mask: int) -> None:
        self.pos += -self.pos & mask


@dataclass
class DataTables:
    """A parsed DATA resource."""

    version: int
    tables: list[TableInfo]
    schemas: list[Schema]
    rows: list[list[Any]]
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

        # --------------------------------------------------------------
        # table headers
        # --------------------------------------------------------------
        reader.seek(table_header_pos + table_header_offset)
        tables: list[TableInfo] = []
        for _ in range(table_count):
            table = TableInfo()
            table.name_offset_pos = reader.tell()
            name_offset = reader.int32()
            table.name_hash = reader.uint32()
            if name_offset != RELOFFSET_NULL:
                table.name = _string_at(
                    reader, table.name_offset_pos + name_offset
                )
            table.schema_offset_pos = reader.tell()
            table.schema_offset = reader.int32()
            table.data_type = reader.uint32()
            table.row_size = reader.uint32()
            table.row_offset_pos = reader.tell()
            table.row_offset = reader.int32()
            table.row_count = reader.uint32()
            tables.append(table)

        row_data_start = reader.tell()

        # --------------------------------------------------------------
        # schemas
        # --------------------------------------------------------------
        reader.seek(schema_pos + schema_offset)
        schemas: list[Schema] = []
        for _ in range(schema_count):
            schema = Schema()
            schema.name_offset_pos = reader.tell()
            name_offset = reader.int32()
            schema.name_hash = reader.uint32()
            if name_offset != RELOFFSET_NULL:
                schema.name = _string_at(
                    reader, schema.name_offset_pos + name_offset
                )
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

        # --------------------------------------------------------------
        # rows
        # --------------------------------------------------------------
        reader.seek(row_data_start)
        schema_offsets = {
            schema.name_offset_pos: index for index, schema in enumerate(schemas)
        }
        schema_by_size: dict[int, int] = {}
        for index, schema in enumerate(schemas):
            schema_by_size.setdefault(schema.schema_size, index)

        rows: list[list[Any]] = []
        for table in tables:
            reader.align(15)
            table_rows: list[Any] = []

            for _ in range(table.row_count):
                if not table.has_schema:
                    table_rows.append(_read_value(reader, table.data_type))
                    reader.align(DataType.alignment(table.data_type) - 1)
                    continue

                absolute_schema = table.schema_offset_pos + table.schema_offset
                schema_index = schema_offsets.get(absolute_schema)
                if schema_index is None:
                    schema_index = schema_by_size.get(table.row_size)
                if schema_index is None:
                    raise DataTableError(
                        f"table {table.name!r}: no schema at "
                        f"offset {absolute_schema}"
                    )
                schema = schemas[schema_index]

                row_start = reader.tell()
                row: dict[Optional[str], Any] = {}
                for column in schema.columns:
                    reader.seek(row_start + column.offset)
                    row[column.name] = _read_value(reader, column.data_type)
                reader.seek(row_start + schema.schema_size)
                table_rows.append(row)

            rows.append(table_rows)

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

    def table(self, name: str) -> tuple[TableInfo, list[Any]]:
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


def _read_value(reader: _Reader, data_type: int) -> Any:
    if data_type == DataType.Boolean:
        return bool(reader.uint8())
    if data_type == DataType.UInt8:
        return reader.uint8()
    if data_type == DataType.Character:
        return reader.chars(1)
    if data_type == DataType.Int8:
        return reader.uint8()
    if data_type == DataType.Int16:
        return reader.int16()
    if data_type == DataType.UInt16:
        return reader.uint16()
    if data_type == DataType.Int32:
        return reader.int32()
    if data_type == DataType.UInt32:
        return reader.uint32()
    if data_type == DataType.Int64:
        return reader.uint64()
    if data_type == DataType.UInt64:
        return reader.uint64()
    if data_type == DataType.Float:
        return reader.float32()
    if data_type == DataType.String:
        return {"startof_mDataOffset": reader.tell(), "mDataOffset": reader.int32()}
    if data_type == DataType.HashedString:
        start = reader.tell()
        return {
            "startof_mDataOffset": start,
            "mDataOffset": reader.int32(),
            "mHash": reader.uint32(),
        }
    if data_type == DataType.Object:
        return {"startof_mDataOffset": reader.tell(), "mDataOffset": reader.int32()}
    if data_type == DataType.Vector:
        start = reader.tell()
        return {
            "startof_mDataOffset": start,
            "mDataOffset": reader.int32(),
            "mCount": reader.uint32(),
        }
    if data_type == DataType.Float2:
        return (reader.float32(), reader.float32())
    if data_type == DataType.Float3:
        return (reader.float32(), reader.float32(), reader.float32())
    if data_type == DataType.Float4:
        return (
            reader.float32(),
            reader.float32(),
            reader.float32(),
            reader.float32(),
        )
    if data_type == DataType.TableSetReference:
        return reader.uint64()
    if data_type == DataType.ResourceKey:
        return {
            "instance": reader.uint64(),
            "type": reader.uint32(),
            "group": reader.uint32(),
        }
    if data_type == DataType.LocalizationKey:
        return reader.uint32()
    if data_type == DataType.Variant:
        start = reader.tell()
        return {
            "startof_mDataOffset": start,
            "mDataOffset": reader.int32(),
            "mTypeHash": reader.uint32(),
        }
    if data_type == DataType.Undefined:
        return None
    raise DataTableError(f"unknown column data type {data_type}")
