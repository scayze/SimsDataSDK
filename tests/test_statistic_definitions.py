"""Typed statistics retain explicit class, localization and winning source."""

from sims4_sdk.catalog import collect_package_data, extract_catalog
from sims4_sdk.core import TUNING_TYPE_ID, ResourceKey
from sims4_sdk.installation import PackageInfo

from conftest import build_package


def _package(path, xml):
    path.write_bytes(build_package([{"type": TUNING_TYPE_ID, "group": 0,
                                     "instance": 99, "data": xml.encode()}]))


def test_statistics_use_explicit_classes_and_keep_mod_source(tmp_path):
    base = tmp_path / "base.package"
    mod = tmp_path / "mod.package"
    _package(base, '''<root>
      <I c="Skill" i="statistic" n="skill_Charisma" s="16699">
        <T n="stat_name">0x1234</T>
      </I>
      <I c="Statistic" i="statistic" n="statistic_skill_like_name" s="2">
        <T n="display_name">0x9876</T>
      </I>
    </root>''')
    _package(mod, '''<root><I c="Skill" i="statistic" n="skill_Charisma_Mod" s="16699">
        <T n="stat_name">0x1234</T>
        <T n="icon">2f7d0004:00000000:0000000000000001</T>
        <L n="ages"><E>ADULT</E><E>TEEN</E></L>
        <E n="skill_level_type">MAJOR</E>
      </I><I c="TunableSkill" i="statistic" n="custom" s="3"/></root>''')
    collected = collect_package_data([PackageInfo(base, "BASE"), PackageInfo(mod, "MOD", True)],
                                     include_world=False, include_relationships=False)
    catalog = extract_catalog(collected.entries, collected.sources, {0x1234: "Charisma"})
    skill = catalog.statistic(16699)
    assert skill.name == "skill_Charisma_Mod" and skill.is_skill is True
    assert skill.display_name == "Charisma" and skill.display_name_raw == "0x1234"
    assert skill.display_name_field == "stat_name"
    assert skill.ages == ["ADULT", "TEEN"] and skill.skill_level_type == "MAJOR"
    assert skill.source.is_mod and skill.source.path == str(mod)
    assert skill.source.resource_key == ResourceKey(TUNING_TYPE_ID, 0, 99)
    assert skill.icon_key is not None
    unknown = catalog.statistic("STATISTIC_SKILL_LIKE_NAME")
    assert unknown.is_skill is None
    assert unknown.display_name is None and unknown.display_name_raw == "0x9876"
    assert unknown.ages is None and unknown.skill_level_type is None
    assert [item.id for item in catalog.find_statistics(is_skill=True)] == [16699, 3]
    assert catalog.to_dict()["statistics"]["16699"]["source"]["is_mod"] is True
    assert '"is_skill": null' in unknown.to_json()
