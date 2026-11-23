import struct
import xml.etree.ElementTree as ET

import pytest

from sims4_sdk.catalog.builder import collect_package_data
from sims4_sdk.catalog.relationships import RELATIONSHIPS_MODULE
from sims4_sdk.catalog.worlds import parse_premade_household
from sims4_sdk.core import DBPF, DBPFError, CombinedTuning, ResourceKey, write_package
from sims4_sdk.core.resource_types import PREMADE_HOUSEHOLD_TYPE_ID
from sims4_sdk.installation import PackageInfo
from sims4_sdk.mods import (
    ModPackageError,
    premade_relationship_override,
    premade_template_override,
    starter_household_override,
)


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
        key, source, name="Müller", funds=23456, sim_traits={7: [1000, 2000]}
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
        starter_household_override(key, source, sim_traits={9: [1]})


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
    module = collected.relationship_modules[RELATIONSHIPS_MODULE].find_module(RELATIONSHIPS_MODULE)
    assert module.findtext("./C/L[@n='FAMILY_RELATIONS_FIXUP']/T") == "123"
    rows = module.findall("./C/L[@n='RELATIONSHIP_MAP']/U")
    assert [[int(child.text) for child in row] for row in rows] == [[1, 2, 6], [2, 1, 7]]
