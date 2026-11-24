"""Lot trait extraction, the saved zone field, and static lot thumbnails."""

from __future__ import annotations

import struct

import pytest

from conftest import build_package
from test_artwork import jpeg
from sims4_sdk.artwork_index import LOT_THUMBNAIL_TYPES, LotThumbnailIndex
from sims4_sdk.catalog.lot_traits import extract_initial_lot_traits, extract_lot_traits
from sims4_sdk.catalog.models import Catalog, TuningSource
from sims4_sdk.core import CombinedTuning, ResourceKey, StringTable
from sims4_sdk.installation import PackageInfo
from sims4_sdk.save.protobuf import _encode_varint, decode
from sims4_sdk.save.schema import SCHEMAS
from sims4_sdk.skills import SkillCurve, SkillCurveError

XML = """<?xml version="1.0"?>
<root>
  <I c="ZoneModifier" i="zone_modifier" m="zone_modifier.zone_modifier" n="lottrait_Romantic" s="100"/>
  <I c="ZoneModifier" i="zone_modifier" m="zone_modifier.zone_modifier" n="lotchallenge_Haunted" s="200"/>
  <I c="ZoneModifier" i="zone_modifier" m="zone_modifier.zone_modifier" n="hidden_modifier" s="300"/>
  <I c="ZoneModifierDisplayInfo" i="user_interface_info" m="zone_modifier.zone_modifier" n="info_Romantic" s="101">
    <T n="zone_modifier_name">0x00000001</T>
    <T n="zone_modifier_description">0x00000002</T>
    <T n="zone_modifier_icon">2f7d0004:00000000:0000000000000abc</T>
    <T n="zone_modifier_reference">100</T>
  </I>
  <I c="ZoneModifierDisplayInfo" i="user_interface_info" m="zone_modifier.zone_modifier" n="info_Haunted" s="201">
    <T n="zone_modifier_name">0x00000003</T>
    <E n="modifier_type">LOT_CHALLENGE</E>
    <T n="zone_modifier_reference">200</T>
  </I>
  <I c="ZoneModifierDisplayInfo" i="user_interface_info" m="zone_modifier.zone_modifier" n="info_Broken" s="401">
    <T n="zone_modifier_reference">999</T>
  </I>
  <M n="zone_modifier.zone_modifier_tuning">
    <C n="ZoneModifierTuning">
      <L n="INITIAL_ZONE_MODIFIERS">
        <U><T n="key">5001</T><L n="value"><T>100</T><T>200</T><T>100</T></L></U>
        <U><T n="key">5002</T><L n="value"/></U>
        <U><L n="value"><T>100</T></L></U>
      </L>
    </C>
  </M>
</root>
"""


def test_lot_traits_come_from_display_info_and_initial_module():
    tuning = CombinedTuning.from_xml(XML)
    entries = {entry.instance_id: entry for entry in tuning}
    source = TuningSource(package="fixture.package", pack="EP05")
    traits = extract_lot_traits(entries, {100: source, 200: source},
                                {1: "Romantic Aura", 2: "Love is in the air", 3: "Haunted"})
    assert set(traits) == {100, 200}
    romantic, haunted = traits[100], traits[200]
    assert (romantic.display_name, romantic.description, romantic.kind) == (
        "Romantic Aura", "Love is in the air", "LOT_TRAIT")
    assert (romantic.display_info_id, romantic.is_challenge, haunted.is_challenge) == (101, False, True)
    assert romantic.icon_key is not None and romantic.icon_key.instance == 0xABC

    initial = extract_initial_lot_traits(tuning)
    assert initial == {5001: [100, 200], 5002: []}
    assert extract_initial_lot_traits(None) == {}

    catalog = Catalog(lot_traits=traits, initial_lot_trait_ids=initial)
    catalog.finalize()
    assert catalog.lot_trait("LOTTRAIT_ROMANTIC") is romantic
    assert catalog.lot_trait(200) is haunted
    assert catalog.find_lot_traits("aura") == [romantic]
    assert catalog.find_lot_traits("", kind="lot_challenge") == [haunted]
    assert "lot_traits" in catalog.to_dict()


def test_saved_zone_decodes_lot_traits():
    data = b"\x09" + struct.pack("<Q", 700)
    for trait in (100, 200):
        data += _encode_varint(20 << 3 | 1) + struct.pack("<Q", trait)
    assert decode(data, "ZoneData", SCHEMAS)["lot_traits"] == [100, 200]


def test_lot_thumbnails_flag_shared_placeholders(tmp_path):
    small, large = LOT_THUMBNAIL_TYPES
    placeholder = jpeg(None, width=400, height=400)
    path = tmp_path / "thumbnails.package"
    path.write_bytes(build_package([
        {"type": small, "group": 2, "instance": 1, "data": jpeg(None, width=256, height=256)},
        {"type": small, "group": 2, "instance": 2, "data": jpeg(None, width=255, height=256)},
        {"type": large, "group": 2, "instance": 1, "data": placeholder},
        {"type": large, "group": 2, "instance": 2, "data": placeholder},
        {"type": large, "group": 2, "instance": 3, "data": jpeg(None, width=399, height=400)},
    ]))

    class InstallationFixture:
        packages = [PackageInfo(path, "BASE")]

    index = LotThumbnailIndex(InstallationFixture())
    assert index.instances == {1, 2, 3}
    result = index.read([1, 3])
    assert result.largest(1).key.type_id == large
    assert result.largest(1).shared
    assert result.largest(1, unique=True).key == ResourceKey(small, 2, 1)
    assert result.largest(3, unique=True).key == ResourceKey(large, 2, 3)


def test_string_table_round_trip():
    data = StringTable(entries={2: "Zwei – 日本", 1: "One"}).to_bytes()
    table = StringTable.parse(data)
    assert dict(table.items()) == {1: "One", 2: "Zwei – 日本"}
    assert table.to_bytes() == data


def test_skill_curve_xp_for_level():
    curve = SkillCurve("mod", [100, 200, 400], "fixture")
    assert [curve.xp_for_level(level) for level in (1, 2, 3)] == [100, 200, 400]
    for level in (0, 4):
        with pytest.raises(SkillCurveError):
            curve.xp_for_level(level)
