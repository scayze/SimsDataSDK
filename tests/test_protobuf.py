import struct

import pytest

from sims4_sdk.save.protobuf import (
    FieldSpec,
    ProtobufError,
    decode,
    iter_fields,
)


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def key(tag: int, wire: int) -> bytes:
    return varint((tag << 3) | wire)


def enc_uint(tag: int, value: int) -> bytes:
    return key(tag, 0) + varint(value)


def enc_str(tag: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    return key(tag, 2) + varint(len(raw)) + raw


def enc_bytes(tag: int, value: bytes) -> bytes:
    return key(tag, 2) + varint(len(value)) + value


def enc_float(tag: int, value: float) -> bytes:
    return key(tag, 5) + struct.pack("<f", value)


def enc_fixed64(tag: int, value: int) -> bytes:
    return key(tag, 1) + value.to_bytes(8, "little")


SCHEMAS = {
    "Test": {
        1: FieldSpec("number"),
        2: FieldSpec("text", "string"),
        3: FieldSpec("floating", "float"),
        4: FieldSpec("numbers", repeated=True),
        5: FieldSpec("fixed", "fixed64", repeated=True),
        6: FieldSpec("child", "message", message="Child"),
        7: FieldSpec("flag", "bool"),
    },
    "Child": {
        1: FieldSpec("value"),
    },
}


def test_missing_nested_schema_raises_protobuf_error() -> None:
    schemas = {"Parent": {1: FieldSpec("child", "message", message="Missing")}}
    with pytest.raises(ProtobufError, match="unknown schema 'Missing'"):
        decode(enc_bytes(1, b""), "Parent", schemas)


def test_scalars_and_message() -> None:
    child = enc_uint(1, 42)
    data = (
        enc_uint(1, 7)
        + enc_str(2, "hello")
        + enc_float(3, 1.5)
        + enc_bytes(6, child)
        + enc_uint(7, 1)
    )
    decoded = decode(data, "Test", SCHEMAS)
    assert decoded["number"] == 7
    assert decoded["text"] == "hello"
    assert decoded["floating"] == pytest.approx(1.5)
    assert decoded["child"] == {"value": 42}
    assert decoded["flag"] is True


def test_repeated_packed_and_unpacked() -> None:
    packed = enc_bytes(4, varint(1) + varint(2) + varint(300))
    unpacked = enc_uint(4, 4) + enc_uint(4, 5)
    decoded = decode(packed + unpacked, "Test", SCHEMAS)
    assert decoded["numbers"] == [1, 2, 300, 4, 5]


def test_repeated_fixed64_packed() -> None:
    packed = enc_bytes(5, (10).to_bytes(8, "little") + (20).to_bytes(8, "little"))
    decoded = decode(packed, "Test", SCHEMAS)
    assert decoded["fixed"] == [10, 20]


def test_fixed64_unpacked_tolerated() -> None:
    decoded = decode(enc_fixed64(5, 99), "Test", SCHEMAS)
    assert decoded["fixed"] == [99]


def test_varint_float_and_double_are_numeric() -> None:
    schema = {"Numbers": {1: FieldSpec("float", "float"), 2: FieldSpec("double", "double")}}
    assert decode(enc_uint(1, 7) + enc_uint(2, 3), "Numbers", schema) == {
        "float": 7.0, "double": 3.0
    }


def test_incompatible_message_wire_type_is_protobuf_error() -> None:
    with pytest.raises(ProtobufError, match="child.*wire type"):
        decode(enc_uint(6, 1), "Test", SCHEMAS)


def test_trailing_zero_stops_parsing() -> None:
    decoded = decode(enc_uint(1, 7) + b"\x00\x00\x00", "Test", SCHEMAS)
    assert decoded["number"] == 7
    assert list(iter_fields(b"\x00\x00")) == []


def test_truncated_raises() -> None:
    data = enc_str(2, "hello")[:-2]
    with pytest.raises(ProtobufError):
        decode(data, "Test", SCHEMAS)


def test_unknown_schema_raises() -> None:
    with pytest.raises(ProtobufError):
        decode(b"", "Missing", SCHEMAS)
