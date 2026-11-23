import struct

from sims4_sdk import list_tray_lots
from sims4_sdk.catalog.models import Catalog
from sims4_sdk.save.protobuf import _encode_varint

from test_artwork import jpeg


def _message(number, data):
    return _encode_varint(number << 3 | 2) + _encode_varint(len(data)) + data


def _integer(number, value):
    return _encode_varint(number << 3) + _encode_varint(value)


def test_list_tray_lots_keeps_build_opaque_and_loads_previews_lazily(tmp_path):
    stem = "0x04080989289100AE"
    blueprint = tmp_path / f"0x00000000!{stem}.blueprint"
    blueprint.write_bytes(b"uninterpreted blueprint")
    preview = tmp_path / f"0x00000002!{stem}.bpi"
    image = jpeg()
    marker = bytes.fromhex("8efc24489b780e3c0200000000000000")
    key = bytes.fromhex("4125e6cd47bab21a")
    preview.write_bytes(struct.pack("<Q", len(image)) + marker
                        + bytes(value ^ key[index % 8] for index, value in enumerate(image)))
    (tmp_path / f"0x00000103!{stem}.bpi").write_bytes(b"unopened")
    lot_metadata = _integer(1, 28614) + _integer(2, 40) + _integer(3, 30) + _integer(11, 100)
    payload = b"".join([
        _integer(1, int(stem, 16)), _integer(2, 2), _message(4, b"Lot"),
        _message(5, b"Description"), _integer(6, 123), _message(7, b"Creator"),
        _message(10, _message(1, lot_metadata)), _integer(11, 63696398670),
    ])
    (tmp_path / f"0x00000002!{stem}.trayitem").write_bytes(struct.pack("<II", 0, len(payload)) + payload)
    household = _integer(2, 1)
    (tmp_path / "0x00000000!0x1234.trayitem").write_bytes(struct.pack("<II", 0, len(household)) + household)

    listing = list_tray_lots(tmp_path, catalog=Catalog(strings={100: "Residential"}))
    assert not listing.errors
    lot, = listing.lots
    assert lot.identifier == stem.lower()
    assert (lot.item.title, lot.item.description, lot.item.creator, lot.item.timestamp) == (
        "Lot", "Description", "Creator", 63696398670
    )
    assert (lot.width, lot.depth, lot.venue_name) == (40, 30, "Residential")
    assert lot.blueprint_files == [blueprint]
    assert len(lot.preview_files) == 2
    assert lot.read_preview().jpeg == image
    assert listing.to_dict()["lots"][0]["item"]["title"] == "Lot"

    blueprint.unlink()
    incomplete = list_tray_lots(tmp_path)
    assert incomplete.lots[0].width == 40
    assert "expected one blueprint" in incomplete.errors[0]["error"]
