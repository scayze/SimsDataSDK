import pytest

from sims4_sdk.core import (
    DBPF,
    DBPFError,
    ResourceKey,
    STRING_TABLE_TYPE_ID,
)

from conftest import build_package


def _write(tmp_path, data: bytes) -> str:
    path = tmp_path / "test.package"
    path.write_bytes(data)
    return str(path)


def test_read_uncompressed_entry(tmp_path) -> None:
    payload = b"hello package"
    package = DBPF(
        _write(
            tmp_path,
            build_package(
                [
                    {
                        "type": STRING_TABLE_TYPE_ID,
                        "group": 0x80000000,
                        "instance": 0x1234,
                        "data": payload,
                    }
                ]
            ),
        )
    )

    assert package.header.magic == b"DBPF"
    assert package.header.major_version == 2
    assert package.header.minor_version == 1
    assert len(package.entries) == 1

    entry = package.entries[0]
    assert entry.key == ResourceKey(STRING_TABLE_TYPE_ID, 0x80000000, 0x1234)
    assert not entry.compressed
    assert package.read_resource(entry) == payload


def test_read_zlib_entry(tmp_path) -> None:
    payload = b"compressed payload " * 32
    package = DBPF(
        _write(
            tmp_path,
            build_package(
                [
                    {
                        "type": STRING_TABLE_TYPE_ID,
                        "group": 0,
                        "instance": 7,
                        "data": payload,
                        "compression": "zlib",
                    }
                ]
            ),
        )
    )

    entry = package.entries[0]
    assert entry.compressed
    assert entry.compression == 0x5A42
    assert package.read_resource(entry) == payload


def test_constant_group_index(tmp_path) -> None:
    # Save files store the group once; entries are then 28 bytes.
    package = DBPF(
        _write(
            tmp_path,
            build_package(
                [
                    {
                        "type": 0x00000006,
                        "group": 0x80000000,
                        "instance": 0x1111222233334444,
                        "data": b"one",
                    },
                    {
                        "type": 0x00000006,
                        "group": 0x80000000,
                        "instance": 0x5555666677778888,
                        "data": b"two",
                    },
                ],
                index_flags=0x02,
                constants={0x02: 0x80000000},
            ),
        )
    )

    assert len(package.entries) == 2
    assert [entry.key.group for entry in package.entries] == [0x80000000, 0x80000000]
    assert package.entries[0].key.instance == 0x1111222233334444
    assert package.read_resource(package.entries[1]) == b"two"


def test_filters_and_lookup(tmp_path) -> None:
    package = DBPF(
        _write(
            tmp_path,
            build_package(
                [
                    {"type": 1, "group": 10, "instance": 1, "data": b"a"},
                    {"type": 2, "group": 10, "instance": 2, "data": b"b"},
                    {"type": 1, "group": 20, "instance": 3, "data": b"c"},
                ]
            ),
        )
    )

    assert [e.key.instance for e in package.iter_entries(type_id=1)] == [1, 3]
    assert [e.key.instance for e in package.iter_entries(group=10)] == [1, 2]
    assert [e.key.instance for e in package.iter_entries(type_id=1, group=20)] == [3]

    entry = package.get_entry(2, 10, 2)
    assert entry is not None
    assert package.read_resource(entry) == b"b"
    assert package.get_entry(9, 9, 9) is None


def test_bad_magic_raises(tmp_path) -> None:
    path = tmp_path / "bad.package"
    path.write_bytes(b"NOPE" + b"\x00" * 92)
    with pytest.raises(DBPFError):
        DBPF(path)


def test_too_small_raises(tmp_path) -> None:
    path = tmp_path / "tiny.package"
    path.write_bytes(b"DBPF")
    with pytest.raises(DBPFError):
        DBPF(path)


def test_resource_key_text_roundtrip() -> None:
    key = ResourceKey(0x220557DA, 0x80000000, 0x0024072D2A2C5142)
    assert str(key) == "220557DA!80000000!0024072D2A2C5142"
    assert ResourceKey.from_text(str(key)) == key


def test_decompress_unknown_id_falls_back_to_raw() -> None:
    assert DBPF.decompress(0x1234, b"raw bytes") == b"raw bytes"
