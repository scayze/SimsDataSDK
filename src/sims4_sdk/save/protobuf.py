"""Minimal schema-driven protobuf reader.

The Sims 4 save files use Google Protocol Buffers for their structured data.  We
do not need a full protobuf runtime; a wire-format reader plus a schema table is
enough to extract the fields the SDK exposes.

Supported wire types: varint, fixed64, length-delimited, fixed32.  Groups are
not used by the save format and are rejected.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

__all__ = [
    "FieldSpec",
    "ProtobufError",
    "decode",
    "decode_message",
    "iter_fields",
]


class ProtobufError(ValueError):
    """Raised when a protobuf stream is malformed or a schema is missing."""


@dataclass(frozen=True)
class FieldSpec:
    """Description of one protobuf field."""

    name: str
    kind: str = "uint"
    #: ``uint``, ``int``, ``bool``, ``enum``, ``float``, ``double``,
    #: ``fixed32``, ``fixed64``, ``string``, ``bytes``, ``message``
    repeated: bool = False
    message: Optional[str] = None


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    start = pos
    while pos < len(data) and shift < 70:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
    raise ProtobufError(f"truncated varint at offset {start}")


def iter_fields(data: bytes) -> Iterator[tuple[int, int, Any]]:
    """Yield ``(field_number, wire_type, raw_value)`` tuples."""
    pos = 0
    total = len(data)
    while pos < total:
        key, pos = _read_varint(data, pos)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 0:
            # Trailing padding / non-protobuf footer.
            return

        if wire_type == 0:  # varint
            value, pos = _read_varint(data, pos)
        elif wire_type == 1:  # fixed64
            end = pos + 8
            if end > total:
                raise ProtobufError("truncated fixed64 field")
            value = data[pos:end]
            pos = end
        elif wire_type == 2:  # length-delimited
            length, pos = _read_varint(data, pos)
            end = pos + length
            if end > total:
                raise ProtobufError(
                    f"truncated length-delimited field {field_number} "
                    f"(wanted {length} bytes at {pos})"
                )
            value = data[pos:end]
            pos = end
        elif wire_type == 5:  # fixed32
            end = pos + 4
            if end > total:
                raise ProtobufError("truncated fixed32 field")
            value = data[pos:end]
            pos = end
        elif wire_type in (3, 4):
            raise ProtobufError("group wire types are not supported")
        else:
            raise ProtobufError(f"unknown wire type {wire_type}")

        yield field_number, wire_type, value


def decode(data: bytes, schema_name: str, schemas: Mapping[str, Mapping[int, FieldSpec]]) -> dict[str, Any]:
    """Decode ``data`` using the named schema."""
    if schema_name not in schemas:
        raise ProtobufError(f"unknown schema {schema_name!r}")
    try:
        return decode_message(data, schemas[schema_name], schemas)
    except ProtobufError as exc:
        raise ProtobufError(f"{schema_name}: {exc}") from exc


def decode_message(
    data: bytes,
    schema: Mapping[int, FieldSpec],
    schemas: Mapping[str, Mapping[int, FieldSpec]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for tag, wire_type, value in iter_fields(data):
        spec = schema.get(tag)
        if spec is None:
            continue

        if spec.kind == "message":
            if spec.message is None:
                raise ProtobufError(f"field {spec.name!r} has no message schema")
            try:
                decoded = decode_message(value, schemas[spec.message], schemas)
            except ProtobufError as exc:
                raise ProtobufError(f"{spec.name} ({spec.message}): {exc}") from exc
        elif spec.kind == "string":
            decoded = value.decode("utf-8", errors="replace")
        elif spec.kind == "bytes":
            decoded = value
        elif spec.kind == "float":
            decoded = _scalar_or_packed(value, wire_type, "float")
        elif spec.kind == "double":
            decoded = _scalar_or_packed(value, wire_type, "double")
        elif spec.kind == "fixed64":
            decoded = _scalar_or_packed(value, wire_type, "fixed64")
        elif spec.kind == "fixed32":
            decoded = _scalar_or_packed(value, wire_type, "fixed32")
        elif spec.kind in ("uint", "enum"):
            decoded = _scalar_or_packed(value, wire_type, "uint")
        elif spec.kind == "int":
            decoded = _signed(_scalar_or_packed(value, wire_type, "uint"))
        elif spec.kind == "bool":
            raw = _scalar_or_packed(value, wire_type, "uint")
            decoded = [bool(v) for v in raw] if isinstance(raw, list) else bool(raw)
        else:
            raise ProtobufError(f"unknown field kind {spec.kind!r}")

        if spec.repeated:
            result.setdefault(spec.name, [])
            if isinstance(decoded, list):
                result[spec.name].extend(decoded)
            else:
                result[spec.name].append(decoded)
        else:
            if isinstance(decoded, list):
                # A non-repeated scalar may still arrive packed by mistake.
                decoded = decoded[0] if decoded else 0
            result[spec.name] = decoded
    return result


def _scalar_or_packed(value: Any, wire_type: int, kind: str) -> Any:
    if wire_type == 2:
        return _unpack(value, kind)
    if kind == "float":
        if wire_type == 1 and len(value) == 8:
            return struct.unpack("<d", value)[0]
        if len(value) != 4:
            raise ProtobufError(f"float field is {len(value)} bytes (wire {wire_type})")
        return struct.unpack("<f", value)[0]
    if kind == "double":
        if wire_type == 5 and len(value) == 4:
            return struct.unpack("<f", value)[0]
        if len(value) != 8:
            raise ProtobufError(f"double field is {len(value)} bytes (wire {wire_type})")
        return struct.unpack("<d", value)[0]
    if kind in ("fixed64", "fixed32"):
        # Tolerate fields whose schema says fixed but that were encoded as varint.
        if wire_type == 0 and isinstance(value, int):
            return value
        return int.from_bytes(value, "little")
    if kind in ("uint", "enum"):
        if wire_type == 0:
            return value
        if wire_type in (1, 5):
            return int.from_bytes(value, "little")
        raise ProtobufError(
            f"varint field has wire type {wire_type} and value {type(value).__name__}"
        )
    raise ProtobufError(f"unsupported scalar kind {kind!r} (wire {wire_type})")


def _unpack(data: bytes, kind: str) -> list[Any]:
    values: list[Any] = []
    pos = 0
    total = len(data)
    if kind in ("float", "fixed32"):
        width = 4
        if total % width:
            raise ProtobufError("packed 4-byte field has a partial element")
        while pos < total:
            chunk = data[pos : pos + width]
            values.append(
                struct.unpack("<f", chunk)[0]
                if kind == "float"
                else int.from_bytes(chunk, "little")
            )
            pos += width
        return values
    if kind in ("double", "fixed64"):
        width = 8
        if total % width:
            raise ProtobufError("packed 8-byte field has a partial element")
        while pos < total:
            chunk = data[pos : pos + width]
            values.append(
                struct.unpack("<d", chunk)[0]
                if kind == "double"
                else int.from_bytes(chunk, "little")
            )
            pos += width
        return values
    if kind == "uint":
        while pos < total:
            value, pos = _read_varint(data, pos)
            values.append(value)
        return values
    raise ProtobufError(f"cannot unpack packed kind {kind!r}")


def _signed(value: Any) -> Any:
    def convert(item: int) -> int:
        if item >= 1 << 63:
            return item - (1 << 64)
        return item

    if isinstance(value, list):
        return [convert(item) for item in value]
    return convert(value)
