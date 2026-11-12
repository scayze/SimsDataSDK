"""Tuning icon extraction (DST/DDS, PNG) without external image dependencies."""

import struct

import pytest

from sims4_sdk import ResourceKey
from sims4_sdk.catalog.models import Milestone, RelationshipBit, Trait
from sims4_sdk.catalog.premades import PremadeAncestor
from sims4_sdk.core.images import (
    GameImage,
    ImageError,
    dds_info,
    decode_image,
    dst_to_dds,
    parse_icon_key,
    parse_image_key,
)


def _dds_header(width: int, height: int, fourcc: bytes) -> bytes:
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 76, 32)
    header[84:88] = fourcc
    return bytes(header)


def test_parse_image_key_accepts_common_spellings():
    assert parse_image_key("2f7d0004:00000000:09481da496b04a84") == ResourceKey(
        0x2F7D0004, 0, 0x09481DA496B04A84
    )
    assert parse_image_key("0x2f7d0004:0x00000000:0x1234") == ResourceKey(
        0x2F7D0004, 0, 0x1234
    )
    assert parse_image_key(None) is None
    assert parse_image_key("bogus") is None
    assert parse_icon_key("2f7d0004:00000000:1234") == ResourceKey(0x2F7D0004, 0, 0x1234)


def test_dst5_unshuffle_roundtrip():
    header = _dds_header(4, 4, b"DST5")
    block = bytes(range(16))  # c0(2) c1(6) c2(4) c3(4)
    c0, c1, c2, c3 = block[0:2], block[2:8], block[8:12], block[12:16]
    dst = header + c0 + c2 + c1 + c3
    out = dst_to_dds(dst)
    assert out[84:88] == b"DXT5"
    assert out[128:] == block
    width, height, fourcc = dds_info(out)
    assert (width, height, fourcc) == (4, 4, "DXT5")


def test_dst1_unshuffle_roundtrip():
    header = _dds_header(4, 4, b"DST1")
    block = bytes(range(8))
    dst = header + block[0:4] + block[4:8]
    out = dst_to_dds(dst)
    assert out[84:88] == b"DXT1"
    assert out[128:] == block


def test_decode_image_png_and_dds():
    ihdr = struct.pack(">IIBBBBB", 8, 6, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4
    img = decode_image(ResourceKey(0x2F7D0004, 0, 1), png)
    assert (img.format, img.width, img.height) == ("PNG", 8, 6)

    dds = _dds_header(16, 32, b"DXT5") + bytes(512)
    img = decode_image(ResourceKey(0x00B2D882, 0, 2), dds)
    assert (img.format, img.width, img.height) == ("DXT5", 16, 32)
    assert img.data.startswith(b"DDS ")


def test_decode_image_rejects_garbage():
    with pytest.raises(ImageError):
        decode_image(ResourceKey(0, 0, 0), b"nope")
    with pytest.raises(ImageError):
        dst_to_dds(_dds_header(4, 4, b"XXXX") + bytes(16))


def test_model_icon_and_thumbnail_keys():
    trait = Trait(
        id=1, name="t", display_name="T", description=None, trait_type="X",
        icon="2f7d0004:00000000:24132068c93561df",
    )
    assert trait.icon_key == ResourceKey(0x2F7D0004, 0, 0x24132068C93561DF)
    assert trait.has_icon
    assert Trait(
        id=2, name="u", display_name="U", description=None, trait_type="X",
    ).icon_key is None

    assert Milestone(
        id=1, name="m", display_name="M", description=None,
        icon="2f7d0004:00000000:abcd",
    ).has_icon
    assert RelationshipBit(
        id=1, name="b", display_name="B", description=None,
        icon="bogus",
    ).icon_key is None
    ancestor = PremadeAncestor(id=1, name="n", full_name="F",
                               thumbnail="2f7d0004:00000000:1111")
    assert ancestor.thumbnail_key == ResourceKey(0x2F7D0004, 0, 0x1111)
    assert ancestor.has_thumbnail


def test_export_includes_icon_key_and_game_image():
    trait = Trait(
        id=1, name="t", display_name="T", description=None, trait_type="X",
        icon="2f7d0004:00000000:24132068c93561df",
    )
    data = trait.to_dict()
    assert data["icon_key"] == "2F7D0004!00000000!24132068C93561DF"

    img = GameImage(key=ResourceKey(0x00B2D882, 0, 5), data=b"DDS ",
                    format="DXT5", width=4, height=4)
    assert img.to_dict() == {
        "key": "00B2D882!00000000!0000000000000005",
        "format": "DXT5", "width": 4, "height": 4,
    }
    assert img.to_dict(include_raw=True)["data"] == b"DDS ".hex()


def test_read_icon_against_game_installation():
    from sims4_sdk import Installation

    try:
        inst = Installation()
    except FileNotFoundError:
        pytest.skip("no Sims 4 installation found")
    img = inst.read_icon("2f7d0004:00000000:24132068c93561df")
    assert img is not None
    assert img.data.startswith(b"DDS ")
    assert img.data[84:88] == b"DXT5"
    assert img.width and img.height
    assert inst.read_icon("bogus") is None
