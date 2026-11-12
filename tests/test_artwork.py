"""Save and Tray artwork parsing without external image dependencies."""

import pytest
from io import BytesIO
from PIL import Image

from conftest import build_package
from sims4_sdk import Artwork, ArtworkError, ResourceKey, decode_artwork, read_tray_image
from sims4_sdk.save import read_save
from sims4_sdk.save.models import SavedSim, TrayHousehold


PNG = b"\x89PNG\r\n\x1a\n" + b"mask-data"
KEY = bytes.fromhex("4125e6cd47bab21a")
HEADER = bytes.fromhex("8efc24489b780e3c0200000000000000")


def image_bytes(image, format):
    output = BytesIO()
    image.save(output, format=format)
    return output.getvalue()


def test_artwork_png_applies_mask_and_handles_missing_mask():
    jpeg_data = image_bytes(Image.new("RGB", (2, 1), "red"), "JPEG")
    mask = Image.new("L", (2, 1))
    mask.putdata([0, 255])
    artwork = Artwork(jpeg_data, image_bytes(mask, "PNG"))
    with Image.open(BytesIO(artwork.to_png())) as result:
        assert result.format == "PNG"
        assert result.mode == "RGBA"
        assert [result.getpixel((x, 0))[3] for x in range(2)] == [0, 255]
    with Image.open(BytesIO(Artwork(jpeg_data).to_png())) as result:
        assert result.getpixel((0, 0))[3] == 255


def test_artwork_png_rejects_mismatched_or_invalid_data():
    jpeg_data = image_bytes(Image.new("RGB", (2, 1)), "JPEG")
    mask = image_bytes(Image.new("L", (1, 1)), "PNG")
    with pytest.raises(ArtworkError, match="dimensions"):
        Artwork(jpeg_data, mask).to_png()
    with pytest.raises(ArtworkError, match="convert"):
        Artwork(b"bad").to_png()


def segment(marker, payload):
    return b"\xff" + bytes([marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def jpeg(mask=PNG, *, split=False, width=30, height=20, kind=b"ALFA"):
    frame = segment(0xC0, b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00")
    alpha = b""
    if mask is not None:
        first = mask[:9] if split else mask
        alpha = segment(0xE0, kind + len(mask).to_bytes(4, "big") + first)
        if split:
            alpha += segment(0xE0, b"ALFX" + mask[9:])
    scan = segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
    return b"\xff\xd8" + alpha + frame + scan + b"\x12\xff\x00\xd9\xff\xd0\x34\xff\xd9"


def wrapped(data):
    payload = data + b"footer!!"
    encoded = bytes(byte ^ KEY[index % len(KEY)] for index, byte in enumerate(payload))
    return len(encoded).to_bytes(8, "little") + HEADER + encoded


def test_decode_artwork_reassembles_alpha_and_ignores_footer():
    data = jpeg(split=True)
    image = decode_artwork(data + b"footer")
    assert image.jpeg == data
    assert image.alpha_mask == PNG and image.alpha_format == "png"
    assert (image.width, image.height) == (30, 20)
    assert image.to_dict()["alpha_mask"] == PNG.hex()
    assert decode_artwork(jpeg(mask=None)).alpha_mask is None
    assert decode_artwork(jpeg(mask=b"\xff\xd8\xff\xd9", kind=b"ALFJ")).alpha_format == "jpeg"


def test_alpha_mask_larger_than_one_jpeg_segment():
    mask = PNG + b"x" * 70_000
    first = mask[:65_525]
    data = (b"\xff\xd8"
            + segment(0xE0, b"ALFA" + len(mask).to_bytes(4, "big") + first)
            + segment(0xE0, b"ALFX" + mask[len(first):])
            + jpeg(mask=None)[2:])
    assert decode_artwork(data).alpha_mask == mask


def test_rejects_malformed_images_and_wrappers(tmp_path):
    with pytest.raises(ArtworkError, match="end marker"):
        decode_artwork(jpeg()[:-2])
    with pytest.raises(ArtworkError, match="length mismatch"):
        decode_artwork(jpeg().replace(len(PNG).to_bytes(4, "big"), (999).to_bytes(4, "big"), 1))
    with pytest.raises(ArtworkError, match="continuation"):
        decode_artwork(b"\xff\xd8" + segment(0xE0, b"ALFXdata") + b"\xff\xd9")
    path = tmp_path / "image.hhi"
    path.write_bytes(wrapped(jpeg())[:-1])
    with pytest.raises(ArtworkError, match="length mismatch"):
        read_tray_image(path)
    path.write_bytes(b"unsupported")
    with pytest.raises(ArtworkError, match="wrapper"):
        read_tray_image(path)


def test_tray_household_images_and_member_portraits(tmp_path):
    hh = TrayHousehold(path=tmp_path / "0x00000000!0x0000000000000123.householdbinary", sims=[SavedSim(sim_id=0x124)])
    (tmp_path / "0x00000002!0x0000000000000123.hhi").write_bytes(wrapped(jpeg(width=30, height=20)))
    (tmp_path / "0x00000003!0x0000000000000123.hhi").write_bytes(wrapped(jpeg(width=60, height=40)))
    (tmp_path / "0x00000013!0x0000000000000124.sgi").write_bytes(wrapped(jpeg()))
    (tmp_path / "0x00000013!0x0000000000000125.sgi").write_bytes(wrapped(jpeg()))
    assert [image.width for image in hh.household_images()] == [30, 60]
    assert hh.household_image().width == 60
    assert hh.portrait(0x124).alpha_mask == PNG
    assert hh.portrait(0x125) is None  # never return another household's image
    assert hh.portrait(0x999) is None


def test_save_artwork_keys_and_bad_images_are_reported(tmp_path):
    path = tmp_path / "test.save"
    image = jpeg()
    path.write_bytes(build_package([
        {"type": 13, "group": 0, "instance": 1, "data": b"\x00"},
        {"type": 20, "group": 0, "instance": 0, "data": image},
        {"type": 20, "group": 0, "instance": 99, "data": image},
        {"type": 20, "group": 1, "instance": 123, "data": b"bad"},
    ]))
    save = read_save(path)
    assert save.thumbnail == image
    assert save.thumbnail_image.alpha_mask == PNG
    assert ResourceKey(20, 0, 99) in save.artwork
    assert save.household_artwork == {}  # no household ID 99 in the save
    assert save.artwork_errors[0]["key"] == str(ResourceKey(20, 1, 123))
    assert save.to_dict()["artwork"][str(ResourceKey(20, 0, 0))]["alpha_format"] == "png"
    assert save.to_dict(include_raw=True)["artwork"][str(ResourceKey(20, 0, 0))]["jpeg"] == image.hex()
