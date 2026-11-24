import struct
import xml.etree.ElementTree as ET

import pytest

from sims4_sdk.catalog.builder import collect_package_data
from sims4_sdk.catalog.relationships import RELATIONSHIPS_MODULE
from sims4_sdk.catalog.worlds import parse_premade_household
from sims4_sdk.core import DBPF, DBPFError, CombinedTuning, ResourceKey, write_package
from sims4_sdk.core.resource_types import PREMADE_HOUSEHOLD_TYPE_ID
from sims4_sdk.installation import PackageInfo
from sims4_sdk.catalog.lot_traits import LOT_TRAITS_MODULE, extract_initial_lot_traits
from sims4_sdk.catalog.relationships import _evaluate_loot
from sims4_sdk.catalog.worlds import StarterCareer, parse_lot_manifest
from sims4_sdk.core.resource_types import (
    ACTION_TUNING_TYPE_ID, LOT_MANIFEST_TYPE_ID, STRING_TABLE_TYPE_ID,
)
from sims4_sdk.core.stbl import LOCALE_CODES, StringTable
from sims4_sdk.mods import (
    ModPackageError,
    StarterMemberEdit,
    initial_lot_traits_override,
    premade_relationship_override,
    premade_template_override,
    relationship_loot,
    starter_household_override,
    starter_household_text,
)
from test_worlds import _bytes_field, _fixed64_field, _float_field, _varint_field


def test_package_creation_round_trip_and_exclusive_output(tmp_path):
    path = tmp_path / "mod.package"
    a = ResourceKey(1, 0xABCD0000, 0x12345678ABCDEF00)
    b = ResourceKey(2, 0, 3)
    assert write_package(path, [(b, b"beta"), (a, b"alpha")]) == path
    dbpf = DBPF(path)
    assert [entry.key for entry in dbpf.entries] == [a, b]
    assert dbpf.read_resource(a) == b"alpha"
    assert dbpf.read_resource(b) == b"beta"
    with pytest.raises(FileExistsError):
        write_package(path, [(a, b"replacement")])
    assert dbpf.read_resource(a) == b"alpha"
    with pytest.raises(DBPFError, match="duplicate"):
        write_package(tmp_path / "duplicate.package", [(a, b"one"), (a, b"two")])
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("version", [0, 2])
def test_starter_override_preserves_other_members_and_unknown_bytes(version):
    def embedded(field, blob):
        return bytes([(field << 3) + 2, len(blob)]) + blob

    other_member = embedded(6, b"\x09" + struct.pack("<Q", 8) + b"\x2a\x03Bob")
    member = b"\x09" + struct.pack("<Q", 7) + b"\x2a\x03Ada"
    unknown = b"\xa0\x06\x81\x00"  # Unknown tag with non-canonical varint.
    house = b"\x1a\x03Old\x20\x01" + embedded(6, member) + other_member + unknown
    payload = embedded(1, house) + b"\x00inner footer"
    header = struct.pack("<I", version) + (bytes(8) if version == 2 else b"")
    source = header + struct.pack("<I", len(payload)) + payload + b"\x00outer footer"
    key = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 0, 5)
    output_key, edited = starter_household_override(
        key, source, name="Müller", funds=23456,
        members={7: StarterMemberEdit(trait_ids=[1000, 2000])},
    )
    assert output_key == key
    assert edited.endswith(unknown + b"\x00inner footer\x00outer footer")
    assert other_member in edited
    declared = struct.unpack_from("<I", edited, len(header))[0]
    assert edited[len(header) + 4 + declared:] == b"\x00outer footer"
    parsed = parse_premade_household(edited)
    assert (parsed.name, parsed.funds) == ("Müller", 23456)
    assert parsed.members[0].trait_ids == [1000, 2000]
    assert parsed.members[1].first_name == "Bob"
    with pytest.raises(ModPackageError, match="do not belong"):
        starter_household_override(key, source, members={9: StarterMemberEdit(trait_ids=[1])})


def _starter(member: bytes) -> tuple[ResourceKey, bytes]:
    payload = _bytes_field(1, b"\x1a\x03BFF" + _bytes_field(6, member))
    return (ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 0, 5),
            struct.pack("<II", 0, len(payload)) + payload)


def test_member_edit_sets_skills_careers_and_aspiration_and_keeps_other_fields():
    # A career entry with extra fields, such as the company name hash (9).
    career = b"".join(_varint_field(number, value) for number, value in
                      ((1, 27932), (2, 32475), (3, 1), (4, 2), (9, 42)))
    history = _bytes_field(2, _varint_field(1, 27932) + _varint_field(2, 32475))
    skills = b"".join(_bytes_field(1, _varint_field(1, skill) + _float_field(2, xp))
                      for skill, xp in ((16704, 100.0), (16703, 1540.0)))
    gameplay = (_bytes_field(10, _bytes_field(1, b"\x01\x02"))
                + _bytes_field(12, _bytes_field(1, career) + history) + _bytes_field(13, skills))
    member = _fixed64_field(1, 7) + _bytes_field(30, gameplay) + _varint_field(34, 25441)
    key, source = _starter(member)
    _, edited = starter_household_override(key, source, description="Bio", members={7: StarterMemberEdit(
        skills={16703: 7600.0, 16704: None, 39397: 100.0},
        careers=[StarterCareer(27932, 32476, track_level=4)],
        aspiration_track_id=123,
    )})
    travis = parse_premade_household(edited).members[0]
    assert travis.trait_ids == [1, 2]
    assert travis.skills == [(16703, 7600.0), (39397, 100.0)]
    assert (travis.career_id, travis.career_track_id) == (27932, 32476)
    assert (travis.career_track_level, travis.career_display_level) == (4, 5)
    assert b"\x48\x2a" in edited  # Company hash kept for the same career.
    assert history in edited
    assert travis.aspiration_track_id == 123
    assert b"\x5a\x03Bio" in edited  # Household field 11.

    _, cleared = starter_household_override(key, source, members={7: StarterMemberEdit(careers=[])})
    assert parse_premade_household(cleared).members[0].careers == []
    with pytest.raises(ModPackageError, match="skill XP"):
        starter_household_override(key, source, members={7: StarterMemberEdit(skills={1: -1})})
    with pytest.raises(ModPackageError, match="once"):
        starter_household_override(key, source, members={7: StarterMemberEdit(
            careers=[StarterCareer(1, 2), StarterCareer(1, 3)])})


@pytest.mark.parametrize("version,size,offset", [(7, 94, 78), (18, 162, 114)])
def test_household_text_rewrites_manifest_keys_and_adds_string_tables(version, size, offset):
    raw = bytearray(size)
    struct.pack_into("<I", raw, 0, version)
    struct.pack_into("<IIQ", raw, offset, 0x11, 0x22, 0x01D9A0186BAD30CD)
    key = ResourceKey(LOT_MANIFEST_TYPE_ID, 0, 0x7A4E)
    resources = starter_household_text((key, bytes(raw)), name="Pals", description="New bio")
    manifest_key, manifest = resources[0]
    assert manifest_key == key and len(manifest) == size
    name_key, description_key, household = struct.unpack_from("<IIQ", manifest, offset)
    assert household == 0x01D9A0186BAD30CD and 0x11 != name_key and 0x22 != description_key
    tables = resources[1:]
    assert len(tables) == len(LOCALE_CODES)
    assert {table_key.instance >> 56 for table_key, _ in tables} == set(LOCALE_CODES)
    assert all(table_key.type_id == STRING_TABLE_TYPE_ID for table_key, _ in tables)
    strings = StringTable.parse(tables[0][1])
    assert (strings[name_key], strings[description_key]) == ("Pals", "New bio")
    assert parse_lot_manifest(manifest, household_ids={household}).household_name_key == name_key

    only_name = starter_household_text((key, bytes(raw)), name="Pals", locales=[0])
    assert len(only_name) == 2
    assert struct.unpack_from("<I", only_name[0][1], offset + 4)[0] == 0x22
    empty = bytearray(raw)
    struct.pack_into("<Q", empty, offset + 8, 0)
    with pytest.raises(ModPackageError, match="no starter household"):
        starter_household_text((key, bytes(empty)), name="Pals")


def test_relationship_loot_sets_tracks_and_bits():
    key, xml = relationship_loot("studio_bella_nancy", friendship=45, romance=-10.5,
                                 bit_ids=[15803, 15803])
    assert key.type_id == ACTION_TUNING_TYPE_ID
    tuning = CombinedTuning.from_xml(xml.decode("utf-8"))
    loot = tuning.find_by_instance_id(key.instance)
    tracks, bits, _, operations = _evaluate_loot(key.instance, {key.instance: loot}, {})
    assert {track.track_id: track.value for track in tracks} == {16650: 45, 16651: -10.5}
    assert bits == [15803] and operations[0].recipients == "Actor"
    with pytest.raises(ModPackageError, match="from -100 to 100"):
        relationship_loot("bad", friendship=101)
    with pytest.raises(ModPackageError, match="supply"):
        relationship_loot("empty")


def test_initial_lot_traits_override_replaces_listed_lots_only(tmp_path):
    source = CombinedTuning.from_xml(f"""
    <root>
      <g><L x="v"><T>144156</T></L></g>
      <M n="{LOT_TRAITS_MODULE}" s="77"><C n="ZoneModifierTuning">
        <L n="INITIAL_ZONE_MODIFIERS">
          <U><T n="key">10</T><r n="value" x="v" /></U>
          <U><T n="key">11</T><L n="value"><T>1</T></L></U>
          <U><T n="key">12</T><L n="value"><T>2</T></L></U>
        </L>
      </C></M>
    </root>""")
    assert extract_initial_lot_traits(source) == {10: [144156], 11: [1], 12: [2]}
    key, xml = initial_lot_traits_override(source, {11: [3, 4, 3], 12: None, 13: [5]})
    assert key == ResourceKey(0x03B33DDF, 0, 77)
    path = write_package(tmp_path / "traits.package", [(key, xml)])
    collected = collect_package_data([PackageInfo(path, "MOD", True)])
    assert extract_initial_lot_traits(collected.tuning_modules[LOT_TRAITS_MODULE]) == {
        10: [144156], 11: [3, 4], 13: [5]}


def test_template_and_relationship_overrides_are_readable_as_mod_tuning(tmp_path):
    source = CombinedTuning.from_xml(f"""
    <root>
      <g><T x="a">123</T><L x="b"><r x="a" /></L></g>
      <I c="PremadeSimTemplate" i="sim_template" n="Test" s="1">
        <r n="keep" x="b" /><T n="remove">old</T>
      </I>
      <M n="{RELATIONSHIPS_MODULE}" s="99"><C n="PremadeSimRelationships">
        <L n="FAMILY_RELATIONS_FIXUP"><r x="a" /></L>
        <L n="RELATIONSHIP_MAP">
          <U><T n="sim_a">1</T><T n="sim_b">2</T><T n="relationship_loot">3</T></U>
          <U><T n="sim_a">1</T><T n="sim_b">4</T><T n="relationship_loot">5</T></U>
        </L>
      </C></M>
    </root>""")
    sim = source.find_by_instance_id(1)
    replacement = ET.fromstring("<T>new</T>")
    template = premade_template_override(sim, {"_traits": replacement, "remove": None})
    relationships = premade_relationship_override(source, {(1, 2): 6, (1, 4): None, (2, 1): 7})
    path = write_package(tmp_path / "mod.package", [template, relationships])
    collected = collect_package_data([PackageInfo(path, "MOD", True)])
    result = collected.entries[1].element
    assert result.findtext("./L[@n='keep']/T") == "123"
    assert result.findtext("./T[@n='_traits']") == "new"
    assert result.find("./T[@n='remove']") is None
    assert replacement.get("n") is None
    assert sim.element.find("./r[@n='keep']") is not None
    module = collected.tuning_modules[RELATIONSHIPS_MODULE].find_module(RELATIONSHIPS_MODULE)
    assert module.findtext("./C/L[@n='FAMILY_RELATIONS_FIXUP']/T") == "123"
    rows = module.findall("./C/L[@n='RELATIONSHIP_MAP']/U")
    assert [[int(child.text) for child in row] for row in rows] == [[1, 2, 6], [2, 1, 7]]
