import pytest

from sims4_sdk.core import fnv1_32, fnv1_64, fnv1a_32, fnv1a_64


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (b"", 0x811C9DC5),
        (b"a", 0x050C5D7E),
        (b"foobar", 0x31F0B262),
    ],
)
def test_fnv1_32_vectors(value: bytes, expected: int) -> None:
    assert fnv1_32(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (b"", 0x811C9DC5),
        (b"a", 0xE40C292C),
        (b"foobar", 0xBF9CF968),
    ],
)
def test_fnv1a_32_vectors(value: bytes, expected: int) -> None:
    assert fnv1a_32(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (b"", 0xCBF29CE484222325),
        (b"a", 0xAF63BD4C8601B7BE),
        (b"foobar", 0x340D8765A4DDA9C2),
    ],
)
def test_fnv1_64_vectors(value: bytes, expected: int) -> None:
    assert fnv1_64(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (b"", 0xCBF29CE484222325),
        (b"a", 0xAF63DC4C8601EC8C),
        (b"foobar", 0x85944171F73967E8),
    ],
)
def test_fnv1a_64_vectors(value: bytes, expected: int) -> None:
    assert fnv1a_64(value) == expected


def test_str_and_bytes_agree() -> None:
    assert fnv1_64("trait_Mean") == fnv1_64(b"trait_Mean")
    assert fnv1_32("hello") == fnv1_32(b"hello")
