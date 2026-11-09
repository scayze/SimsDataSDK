import pytest

from sims4_sdk.core import RefPackError, decompress_refpack, is_refpack


def _literal_stream(payload: bytes, *, flags: int = 0x10) -> bytes:
    """Build a RefPack stream that is one literal run followed by a stop code."""
    if not 4 <= len(payload) <= 112:
        raise ValueError("helper only supports 4..112 literal bytes")
    control = 0xE0 | ((len(payload) - 4) >> 2)
    assert ((control & 0x1F) << 2) + 4 == len(payload)
    assert control <= 0xFB
    header = bytes([flags, 0xFB])
    if flags & 0x80:
        header += len(payload).to_bytes(4, "big")
    else:
        header += len(payload).to_bytes(3, "big")
    return header + bytes([control]) + payload + b"\xFC"


@pytest.mark.parametrize("flags", [0x10, 0x50, 0x90, 0xD0])
def test_literal_decompression(flags: int) -> None:
    data = _literal_stream(b"ABCD", flags=flags)
    assert is_refpack(data)
    assert decompress_refpack(data) == b"ABCD"


def test_longer_literal_run() -> None:
    payload = bytes(range(4, 36))
    assert decompress_refpack(_literal_stream(payload)) == payload


def test_four_byte_prefix() -> None:
    stream = _literal_stream(b"WXYZ")
    assert is_refpack(b"\x00\x00\x00\x00" + stream)
    assert decompress_refpack(b"\x00\x00\x00\x00" + stream) == b"WXYZ"


def test_not_refpack() -> None:
    assert not is_refpack(b"")
    assert not is_refpack(b"STBL")
    assert not is_refpack(b"x\x9c")


def test_bad_magic_raises() -> None:
    with pytest.raises(RefPackError):
        decompress_refpack(b"STBL\x05\x00\x00")


def test_truncated_stream_raises() -> None:
    data = _literal_stream(b"ABCD")
    with pytest.raises(RefPackError):
        decompress_refpack(data[:-4])


def test_back_reference_copy() -> None:
    # Literal "ABab" (4 bytes), then a 0x00 copy of length 3 and offset 4
    # (b1 = 3), which copies "ABa" from the start of the output.
    stream = b"\x10\xFB\x00\x00\x07" + b"\xE0" + b"ABab" + b"\x00\x03" + b"\xFC"
    assert decompress_refpack(stream) == b"ABab" + b"ABa"
