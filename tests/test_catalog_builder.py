"""Unit tests for catalog package collection."""

from __future__ import annotations

import pytest
import struct

from sims4_sdk.catalog import build_static, collect_package_data, load_static
from sims4_sdk.core import COMBINED_TUNING_TYPE_ID, PREMADE_HOUSEHOLD_TYPE_ID, STRING_TABLE_TYPE_ID, TUNING_TYPE_ID, CombinedTuning, ResourceKey
from sims4_sdk.installation import Installation, PackageInfo

from conftest import build_package, build_stbl

XML = """<?xml version="1.0" encoding="utf-8"?>
<combined>
  <I c="Trait" i="trait" m="traits.traits" n="trait_Test" s="1234">
    <T n="display_name">Test</T>
  </I>
</combined>
"""

OTHER_XML = """<?xml version="1.0" encoding="utf-8"?>
<combined>
  <I c="Trait" i="trait" m="traits.traits" n="trait_Other" s="5678">
    <T n="display_name">Other</T>
  </I>
</combined>
"""


def _package(tmp_path, name: str, payload: bytes) -> PackageInfo:
    path = tmp_path / name
    path.write_bytes(
        build_package(
            [
                {
                    "type": COMBINED_TUNING_TYPE_ID,
                    "group": 0,
                    "instance": 1,
                    "data": payload,
                    "compression": "zlib",
                }
            ]
        )
    )
    return PackageInfo(path, "BASE")


def test_identical_combined_tuning_is_parsed_once(tmp_path, monkeypatch) -> None:
    packages = [
        _package(tmp_path, "SimulationPreload.package", XML.encode("utf-8")),
        _package(tmp_path, "SimulationDeltaBuild0.package", XML.encode("utf-8")),
    ]

    calls = []
    original = CombinedTuning.parse

    def counting_parse(data: bytes) -> CombinedTuning:
        calls.append(data)
        return original(data)

    monkeypatch.setattr(CombinedTuning, "parse", staticmethod(counting_parse))

    data = collect_package_data(packages, include_world=False)

    assert len(calls) == 1
    assert data.entries[1234].name == "trait_Test"


def test_different_combined_tuning_is_parsed_separately(tmp_path, monkeypatch) -> None:
    packages = [
        _package(tmp_path, "a.package", XML.encode("utf-8")),
        _package(tmp_path, "b.package", OTHER_XML.encode("utf-8")),
    ]

    calls = []
    original = CombinedTuning.parse

    def counting_parse(data: bytes) -> CombinedTuning:
        calls.append(data)
        return original(data)

    monkeypatch.setattr(CombinedTuning, "parse", staticmethod(counting_parse))

    data = collect_package_data(packages, include_world=False)

    assert len(calls) == 2
    assert set(data.entries) == {1234, 5678}


def test_scan_preserves_sources_raw_world_and_reports_failed_inputs(tmp_path) -> None:
    member = b"\x09" + struct.pack("<Q", 7) + b"\x2a\x03Sam"
    household = b"\x1a\x06Family\x32" + bytes([len(member)]) + member
    payload = b"\x0a" + bytes([len(household)]) + household
    resource = struct.pack("<II", 0, len(payload)) + payload
    path = tmp_path / "content.package"
    path.write_bytes(build_package([
        {"type": COMBINED_TUNING_TYPE_ID, "group": 3, "instance": 1, "data": XML.encode()},
        {"type": COMBINED_TUNING_TYPE_ID, "group": 4, "instance": 2, "data": b"not tuning"},
        {"type": TUNING_TYPE_ID, "group": 5, "instance": 3, "data": b"<invalid"},
        {"type": PREMADE_HOUSEHOLD_TYPE_ID, "group": 6, "instance": 8, "data": resource},
        {"type": PREMADE_HOUSEHOLD_TYPE_ID, "group": 6, "instance": 9, "data": b"invalid"},
    ]))
    bad = PackageInfo(tmp_path / "missing.package", "BASE")
    good = PackageInfo(path, "BASE")
    data = build_static(Installation(tmp_path, include_mods=False), packages=[bad, good],
                        strings_packages=[], use_cache=False)
    assert {issue.stage for issue in data.catalog.diagnostics} == {
        "package_open", "combined_tuning", "tuning_read", "household"
    }
    broken = next(issue for issue in data.catalog.diagnostics if issue.stage == "combined_tuning")
    assert broken.package_path == str(path)
    assert broken.resource_key == ResourceKey(COMBINED_TUNING_TYPE_ID, 4, 2)
    assert broken.to_dict()["resource_key"] == str(broken.resource_key)
    assert broken.recoverable is True
    assert broken.to_dict()["recoverable"] is True
    assert broken.to_dict()["unsupported_format"] is None
    trait = data.catalog.traits[1234]
    assert trait.source.path == str(path)
    assert trait.source.resource_key == ResourceKey(COMBINED_TUNING_TYPE_ID, 3, 1)
    assert trait.to_dict()["source"]["resource_key"] == str(trait.source.resource_key)
    record = data.world.households[8]
    assert record.raw == resource and record.source.resource_key == ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 6, 8)
    assert data.world.household_resources[record.source.resource_key] is record
    assert record.member(7).first_name == "Sam"
    assert data.world.find_members(7) == [(record, record.member(7))]
    snapshot = data.save(tmp_path / "static.pkl")
    loaded = data.load(snapshot)
    assert loaded.world.households[8].raw == resource
    serialized = loaded.to_dict()
    assert serialized["world"]["households"]["8"]["members"][0]["sim_id"] == 7
    assert "raw" not in serialized["world"]["households"]["8"]
    assert loaded.to_dict(include_raw=True)["world"]["households"]["8"]["raw"] == resource.hex()


def test_world_preserves_distinct_resource_groups_and_last_override(tmp_path) -> None:
    from sims4_sdk.core import LOT_MANIFEST_TYPE_ID

    def household_resource(name):
        hh = b"\x1a" + bytes([len(name)]) + name
        payload = b"\x0a" + bytes([len(hh)]) + hh
        return struct.pack("<II", 0, len(payload)) + payload

    def source(name, data):
        path = tmp_path / name
        path.write_bytes(build_package(data))
        return PackageInfo(path, "BASE")

    packages = [
        source("first.package", [
            {"type": PREMADE_HOUSEHOLD_TYPE_ID, "group": 1, "instance": 8, "data": household_resource(b"A")},
            {"type": PREMADE_HOUSEHOLD_TYPE_ID, "group": 2, "instance": 8, "data": household_resource(b"B")},
            {"type": LOT_MANIFEST_TYPE_ID, "group": 1, "instance": 9, "data": struct.pack("<IIII", 0, 10, 0, 0)},
            {"type": LOT_MANIFEST_TYPE_ID, "group": 2, "instance": 9, "data": struct.pack("<IIII", 0, 20, 0, 0)},
        ]),
        source("override.package", [
            {"type": PREMADE_HOUSEHOLD_TYPE_ID, "group": 1, "instance": 8, "data": household_resource(b"C")},
            {"type": LOT_MANIFEST_TYPE_ID, "group": 1, "instance": 9, "data": struct.pack("<IIII", 0, 30, 0, 0)},
        ]),
    ]
    world = collect_package_data(packages).world
    key_a = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 1, 8)
    key_b = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 2, 8)
    assert world.household_resources[key_a].name == "C"
    assert world.household_resources[key_b].name == "B"
    assert world.households[8].name == "C"
    assert world.lot_resources[ResourceKey(LOT_MANIFEST_TYPE_ID, 1, 9)].lot_name_key == 30
    assert world.lot_resources[ResourceKey(LOT_MANIFEST_TYPE_ID, 2, 9)].lot_name_key == 20
    assert world.lots[9].lot_name_key == 30


def test_static_cache_includes_string_packages_and_file_changes(tmp_path) -> None:
    tuning = _package(tmp_path, "tuning.package", XML.replace("<T n=\"display_name\">Test</T>", "<T n=\"display_name\">0x1234</T>").encode())
    def strings_file(name, text):
        path = tmp_path / name
        path.write_bytes(build_package([{"type": STRING_TABLE_TYPE_ID, "group": 0, "instance": 0,
                                        "data": build_stbl([(0x1234, text)])}]))
        return PackageInfo(path, "BASE")

    first = strings_file("one.package", "First")
    second = strings_file("two.package", "Second")
    install = Installation(tmp_path, include_mods=False)
    cache = tmp_path / "cache"
    a = build_static(install, packages=[tuning], strings_packages=[first], cache_dir=cache)
    assert a.catalog.traits[1234].display_name == "First"
    assert load_static(install, packages=[tuning], strings_packages=[second], cache_dir=cache) is None
    b = build_static(install, packages=[tuning], strings_packages=[second], cache_dir=cache)
    assert b.catalog.traits[1234].display_name == "Second"
    assert load_static(install, packages=[tuning], strings_packages=[first], cache_dir=cache).catalog.traits[1234].display_name == "First"
    strings_file("one.package", "A changed and longer translation")
    assert load_static(install, packages=[tuning], strings_packages=[first], cache_dir=cache) is None
    c = build_static(install, packages=[tuning], strings_packages=[first], cache_dir=cache)
    assert c.catalog.traits[1234].display_name == "A changed and longer translation"


def test_string_failures_are_reported_without_losing_other_strings(tmp_path) -> None:
    from sims4_sdk.catalog.strings import load_strings

    path = tmp_path / "strings.package"
    path.write_bytes(build_package([
        {"type": STRING_TABLE_TYPE_ID, "group": 0, "instance": 1, "data": b"bad"},
        {"type": STRING_TABLE_TYPE_ID, "group": 0, "instance": 2, "data": build_stbl([(0x1234, "Available")])},
    ]))
    issues = []
    strings = load_strings(Installation(tmp_path, include_mods=False),
                           packages=[PackageInfo(tmp_path / "missing.package", "BASE"), PackageInfo(path, "BASE")],
                           diagnostics=issues)
    assert strings[0x1234] == "Available"
    assert [issue.stage for issue in issues] == ["string_package_open", "string_table"]
    assert issues[1].resource_key == ResourceKey(STRING_TABLE_TYPE_ID, 0, 1)
