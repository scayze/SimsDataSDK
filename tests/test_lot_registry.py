import struct
from types import SimpleNamespace

import pytest

from sims4_sdk import LotRegistry, SaveFile, SavedHousehold, SaveZone
from sims4_sdk.catalog.lot_registry import build_lot_registry, overlay_save
from sims4_sdk.catalog.models import Catalog, TuningSource
from sims4_sdk.catalog.static import StaticData
from sims4_sdk.catalog.worlds import WorldData, parse_lot_manifest
from sims4_sdk.core import DBPF, ResourceKey, write_package
from sims4_sdk.core.fnv import fnv1_32, fnv1_64
from sims4_sdk.core.lot_architecture import architecture_venue_id
from sims4_sdk.core.resource_types import (
    LOT_DESCRIPTION_TYPE_ID, LOT_MANIFEST_TYPE_ID, REGION_DESCRIPTION_TYPE_ID,
    STREET_DESCRIPTION_TYPE_ID, WORLD_LOT_ARCHITECTURE_TYPE_ID,
)
from sims4_sdk.mods import ModPackageError, move_starter_household
from sims4_sdk.save.protobuf import _encode_varint

from conftest import build_package


def _architecture(venue_id):
    record = struct.pack("<IQ", 6, venue_id)
    return (struct.pack("<4s9I", b"LDNB", 3, 0, 0, 1, 56, 88, 40, 1, 64)
            + record + bytes(4) + struct.pack("<Q6I", 1, 0xE6BBD7DE, 0, 0, 0, 0, 1)
            + bytes(3) + len(record).to_bytes(3, "big"))


def _site(world, ordinal, starter_id):
    lot_id = 200 + ordinal
    description_id = 300 + ordinal
    template_id = 400 + ordinal
    key = ResourceKey(LOT_MANIFEST_TYPE_ID, 0, 500 + ordinal)
    world.geography[ResourceKey(LOT_DESCRIPTION_TYPE_ID, 0, description_id)] = (
        struct.pack("<IQIIBB", 12, 99, lot_id, 1700, 40, 30)
    )
    data = bytearray(162)
    struct.pack_into("<II", data, 0, 18, ordinal)
    struct.pack_into("<Q", data, 90, template_id)
    struct.pack_into("<Q", data, 106, description_id)
    if starter_id:
        data[83] = 2
        struct.pack_into("<IIQ", data, 114, 3, 4, starter_id)
    world.lot_resources[key] = parse_lot_manifest(
        bytes(data), instance=key.instance, household_ids={starter_id},
        source=TuningSource(package="fixture.package", pack="BASE", resource_key=key),
    )


def test_lot_registry_and_relocation_round_trip(tmp_path):
    region = ResourceKey(REGION_DESCRIPTION_TYPE_ID, 0, 98)
    street = ResourceKey(STREET_DESCRIPTION_TYPE_ID, 0, 99)
    world = WorldData(geography={
        region: struct.pack("<II", 12, 5),
        street: struct.pack("<4IQI", 11, 6, 0, 0, 98, 4) + b"Test",
    }, venue_names={28614: "Residential", 16874: "Library"})
    _site(world, 1, 1234)
    _site(world, 2, 0)
    strings = {1: "Origin", 2: "Destination", 3: "Family", 5: "Region", 6: "Street"}
    static = StaticData(catalog=Catalog(strings=strings, initial_lot_trait_ids={501: [144156]}),
                        world=world)
    path = tmp_path / "Data/Shared/Worlds/Areas/Test.world"
    path.parent.mkdir(parents=True)
    architecture = _architecture(28614)
    path.write_bytes(build_package([
        {"type": WORLD_LOT_ARCHITECTURE_TYPE_ID, "group": 0,
         "instance": fnv1_64(f"1-{template:08x}"),
         "data": struct.pack("<I", len(architecture)) + architecture}
        for template in (401, 402)
    ]))
    base = build_lot_registry(static, SimpleNamespace(install_dir=tmp_path))
    assert isinstance(base, LotRegistry)
    origin, destination = base.lot("ORIGIN"), base.lot(202)
    assert base.find_lots("stin", region_id=98, street_id=99) == [destination]
    assert (origin.household_name, origin.occupancy, destination.occupancy) == ("Family", "occupied", "vacant")
    assert (destination.region_name, destination.street_name, destination.world_id) == ("Region", "Street", fnv1_32("test"))
    assert (destination.width, destination.depth, destination.venue_name) == (40, 30, "Residential")
    assert destination.to_dict()["manifest_key"] == str(destination.manifest_key)
    assert (origin.house_description_id, origin.lot_trait_ids, destination.lot_trait_ids) == (501, (144156,), ())

    output = write_package(tmp_path / "move.package", move_starter_household(world, origin, destination))
    package = DBPF(output)
    for lot, expected in ((origin, None), (destination, 1234)):
        data = package.read_resource(lot.manifest_key)
        original = world.lot_resources[lot.manifest_key].raw
        assert data[:83] + data[84:114] + data[130:] == original[:83] + original[84:114] + original[130:]
        parsed = parse_lot_manifest(data, household_ids={1234})
        assert parsed.household_id == expected
        assert parsed.lot_description_id == lot.lot_description_id

    saved_architecture = _architecture(16874)
    save_path = tmp_path / "live.save"
    save_path.write_bytes(build_package([{"type": 6, "group": 0, "instance": 700,
        "data": b"\x09" + struct.pack("<Q", 700)
        + b"\x12" + _encode_varint(len(saved_architecture)) + saved_architecture}]))
    save = SaveFile(save_path, zones={
        700: SaveZone(700, "Renamed", lot_id=202, household_id=900, lot_description_id=302,
                      lot_template_id=402, venue_id=28614, lot_trait_ids=[7]),
        701: SaveZone(701, "Unlinked", lot_id=209, household_id=0, lot_description_id=309),
    }, households={900: SavedHousehold(900, name="Family", home_zone=700)})
    overlaid = overlay_save(base, save, world.venue_names)
    lot = overlaid.zone(700)
    assert (lot.name, lot.household_name, lot.venue_name, lot.manifest_key) == (
        "Renamed", "Family", "Library", destination.manifest_key
    )
    assert overlaid.zone(701).occupancy == "vacant"
    assert (lot.lot_trait_ids, overlaid.lot(201).lot_trait_ids) == ((7,), None)
    assert overlaid.lot(201).occupancy == "unknown"
    assert base.lot(201).occupancy == "occupied"
    with pytest.raises(ModPackageError):
        move_starter_household(world, lot, destination)


def test_architecture_venue_reads_the_settings_record_only():
    data = _architecture(16874)
    assert architecture_venue_id(data) == 16874
    assert architecture_venue_id(data[:-1]) is None
    assert architecture_venue_id(data.replace(b"LDNB", b"TEST")) is None
