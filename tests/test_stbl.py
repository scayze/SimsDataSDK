import pytest

from sims4_sdk.core import STBLError, StringTable, locale_from_instance, locale_name

from conftest import build_stbl


def test_roundtrip() -> None:
    data = build_stbl([(0x12345678, "Hello"), (0xABCDEF01, "World")])
    table = StringTable.parse(data)

    assert len(table) == 2
    assert table.version == 5
    assert table[0x12345678] == "Hello"
    assert table.get(0xABCDEF01) == "World"
    assert 0x12345678 in table
    assert dict(table.items()) == {0x12345678: "Hello", 0xABCDEF01: "World"}


def test_empty_table() -> None:
    table = StringTable.parse(build_stbl([]))
    assert len(table) == 0


def test_trailing_null_is_stripped() -> None:
    table = StringTable.parse(build_stbl([(1, "abc\x00")]))
    assert table[1] == "abc"


def test_unicode() -> None:
    text = "Zürich – 日本語 – 🎉"
    table = StringTable.parse(build_stbl([(42, text)]))
    assert table[42] == text


def test_bad_magic_raises() -> None:
    data = bytearray(build_stbl([(1, "x")]))
    data[0:4] = b"NOPE"
    with pytest.raises(STBLError):
        StringTable.parse(bytes(data))


def test_truncated_raises() -> None:
    data = build_stbl([(1, "hello"), (2, "world")])
    with pytest.raises(STBLError):
        StringTable.parse(data[:-4])


def test_merge_prefers_new_values() -> None:
    base = StringTable.from_entries({1: "old", 2: "keep"})
    override = StringTable.from_entries({1: "new"})
    merged = base.merge(override)
    assert merged[1] == "new"
    assert merged[2] == "keep"
    assert base[1] == "old"


def test_locale_helpers() -> None:
    assert locale_from_instance(0x0024072D2A2C5142) == 0x00
    assert locale_from_instance(0x0724072D2A2C5142) == 0x07
    assert locale_name(0x00) == "ENG_US"
    assert locale_name(0x07) == "FRA_FR"
