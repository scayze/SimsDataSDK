import struct

from conftest import build_package
from sims4_sdk.catalog.builder import add_simdata_statistics, collect_package_data, extract_catalog
from sims4_sdk.core.resource_types import SIMDATA_TYPE_ID, TUNING_TYPE_ID
from sims4_sdk.installation import PackageInfo


def make_stat_data(name="skill_FromData", schema="Skill", label=0x1234):
    """Small DATA resource with one named table and two typed columns."""
    buf = bytearray(144)
    buf[0:4] = b"DATA"
    struct.pack_into("<Iiiii", buf, 4, 0x100, 16, 1, 64, 1)
    # Table header at 24, row at aligned offset 64, schema at 80.
    struct.pack_into("<iIiIIiI", buf, 24, 0, 0, 48, 13, 16, 20, 1)
    struct.pack_into("<Iq", buf, 64, label, 0)  # enum is explicitly zero
    # Second column begins at offset 4, so int64 is at row+4.
    struct.pack_into("<iIIIiI", buf, 80, 0, 0, 0, 16, 8, 2)
    struct.pack_into("<iIHHIi", buf, 104, 0, 0, 20, 0, 0, 0)
    struct.pack_into("<iIHHIi", buf, 124, 0, 0, 8, 0, 4, 0)
    def string_ref(pos, text):
        encoded = text.encode() + b"\0"
        struct.pack_into("<i", buf, pos, len(buf) - pos)
        buf.extend(encoded)
    string_ref(24, name)
    string_ref(80, schema)
    string_ref(104, "stat_name")
    string_ref(124, "skill_level_type")
    return bytes(buf)


def test_simdata_only_and_xml_precedence_with_mod_groups(tmp_path):
    base, mod = tmp_path / "base.package", tmp_path / "mod.package"
    def resource(kind, group, instance, data):
        return {"type": kind, "group": group, "instance": instance, "data": data}
    base.write_bytes(build_package([
        resource(SIMDATA_TYPE_ID, 0x009BC58E, 100, make_stat_data()),
        resource(SIMDATA_TYPE_ID, 0x009BC58E, 200, make_stat_data("duplicate")),
        resource(TUNING_TYPE_ID, 0, 200, b'<I c="Statistic" i="statistic" m="statistics.statistic" n="xml_wins" s="200"/>'),
    ]))
    mod.write_bytes(build_package([
        resource(SIMDATA_TYPE_ID, 123, 300, make_stat_data("mod_skill")),
        resource(SIMDATA_TYPE_ID, 123, 400, make_stat_data("not_a_skill", "Commodity")),
        resource(SIMDATA_TYPE_ID, 0x009BC58E, 500, b"DATA\x00"),
    ]))
    data = collect_package_data([PackageInfo(base, "BASE"), PackageInfo(mod, "MOD", True)],
                                include_world=False, include_relationships=False)
    catalog = extract_catalog(data.entries, data.sources, {})
    add_simdata_statistics(catalog, data, {0x1234: "Localized"})
    assert catalog.statistic(100).display_name == "Localized"
    assert catalog.statistic(100).skill_level_type_raw == 0
    assert catalog.statistic(100).source.resource_key.type_id == SIMDATA_TYPE_ID
    assert catalog.statistic(200).name == "xml_wins"
    assert catalog.statistic("MOD_SKILL").source.is_mod
    assert catalog.statistic(400) is None
    assert any(issue.stage == "simdata_statistic" and issue.resource_key.instance == 500
               for issue in data.diagnostics)
