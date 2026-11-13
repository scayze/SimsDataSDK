import json
from types import SimpleNamespace

from conftest import build_package
from sims4_sdk.core import COMBINED_TUNING_TYPE_ID, TUNING_TYPE_ID
from sims4_sdk.installation import PackageInfo
from sims4_sdk.skill_discovery import discover_skill_curves
from sims4_sdk.skills import convert_skill_xp


def tuning(amounts, name="MAJOR"):
    values = "".join(f"<T>{x}</T>" for x in amounts)
    return (f'<root><M n="statistics.skill"><C n="Skill"><L n="SKILL_LEVEL_LIST">'
            f'<U><E n="key">{name}</E><L n="value">{values}</L></U>'
            '</L></C></M></root>').encode()


def write_package(path, contents):
    path.write_bytes(build_package([{"type": typ, "group": 0, "instance": instance, "data": data}
                                   for typ, instance, data in contents]))


def test_discovery_uses_ordered_tuning_and_explicit_skill_type(tmp_path):
    base, mod = tmp_path / "base.package", tmp_path / "mod.package"
    write_package(base, [(COMBINED_TUNING_TYPE_ID, 1, tuning([100, 1440, 2160, 3600]))])
    write_package(mod, [(TUNING_TYPE_ID, 2, tuning([100, 200])),
                        (COMBINED_TUNING_TYPE_ID, 3, tuning([100, 1440, 2160, 3600]))])
    result = discover_skill_curves([PackageInfo(base, "BASE"), PackageInfo(mod, "MOD", True)])
    skill = SimpleNamespace(is_skill=True, skill_level_type="MAJOR")
    curve = result.for_skill(skill)
    assert result.complete and result.package_path == str(mod) and result.resource_key.instance == 3
    assert curve.thresholds == (100, 1540, 3700, 7300)
    assert convert_skill_xp(99, curve).level is None
    assert convert_skill_xp(100, curve).level == 1
    assert convert_skill_xp(1539.99, curve).level == 1
    assert convert_skill_xp(1540, curve).level == 2
    assert convert_skill_xp(7300, curve).level == 4
    assert convert_skill_xp(100, curve).assigned is None
    assert result.for_skill(SimpleNamespace(is_skill=True, skill_level_type="CUSTOM")) is None
    assert result.for_skill(SimpleNamespace(is_skill=None, skill_level_type="MAJOR")) is None
    assert json.loads(result.to_json())["curves"]["MAJOR"]["thresholds"] == [100, 1540, 3700, 7300]


def test_references_and_incomplete_scans_are_explicit(tmp_path):
    base, broken = tmp_path / "base.package", tmp_path / "broken.package"
    xml = b'''<root><g><T x="a">MAJOR</T><T x="b">100</T></g>
      <M n="statistics.skill"><C n="Skill"><L n="SKILL_LEVEL_LIST">
      <U><r n="key" x="a"/><L n="value"><r x="b"/><T>1440</T></L></U>
      </L></C></M></root>'''
    write_package(base, [(COMBINED_TUNING_TYPE_ID, 1, xml)])
    write_package(broken, [(COMBINED_TUNING_TYPE_ID, 2, tuning([100, -1]))])
    result = discover_skill_curves([PackageInfo(base, "BASE"), PackageInfo(broken, "MOD", True)])
    skill = SimpleNamespace(is_skill=True, skill_level_type="MAJOR")
    assert not result.complete and result.for_skill(skill) is None
    assert result.for_skill(skill, allow_incomplete=True).thresholds == (100, 1540)
    assert result.diagnostics[0].resource_key.instance == 2
