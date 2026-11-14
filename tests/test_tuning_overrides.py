import json

from conftest import build_package
from sims4_sdk.catalog import build_static
from sims4_sdk.catalog.builder import build_catalog
from sims4_sdk.core import COMBINED_TUNING_TYPE_ID, ResourceKey
from sims4_sdk.core.fnv import fnv1_32
from sims4_sdk.installation import Installation, PackageInfo


def test_premade_pack_attribution_preserves_official_history(tmp_path):
    def package(name, pack, mod=False):
        path = tmp_path / name
        data = b'<I c="PremadeSimTemplate" n="premade_Test" s="1234" />'
        path.write_bytes(build_package([{"type": COMBINED_TUNING_TYPE_ID, "group": 0,
                                        "instance": 1, "data": data}]))
        return PackageInfo(path, pack, mod)

    ep = package("ep.package", "EP06")
    mod = package("mod.package", "MOD", True)
    other = package("other.package", "GP08")
    installation = Installation(tmp_path, include_mods=False)
    def build(packages):
        return build_static(installation, packages=packages, strings_packages=[], use_cache=False).sim(1234)

    assert build([ep]).pack_id == "EP06"
    assert build([ep, mod]).pack_id == "EP06"
    assert build([mod]).pack_id is None
    assert build([ep, other]).pack_id is None


def test_mod_tuning_history_and_class_hashed_xml(tmp_path):
    def make(name, entries, *, mod=False):
        path = tmp_path / name
        path.write_bytes(build_package(entries))
        return PackageInfo(path, "MOD" if mod else "BASE", mod)

    def combined(name):
        return f'<I c="Skill" n="{name}" s="1234"><T n="stat_name">Label</T></I>'.encode()

    def item(resource_type, instance, data):
        return {"type": resource_type, "group": 7, "instance": instance, "data": data}

    hashed = fnv1_32("skill")
    base = make("base.package", [item(COMBINED_TUNING_TYPE_ID, 1, combined("base"))])
    repeat = make("repeat.package", [item(COMBINED_TUNING_TYPE_ID, 1, combined("base"))])
    mod = make("mod.package", [item(hashed, 1234, combined("mod")),
                               item(hashed, 5678, b'<I c="Skill" n="no_id"/>')], mod=True)
    installation = Installation(tmp_path, include_mods=False)
    packages = [base, repeat, mod]
    catalog = build_catalog(installation, packages=packages, use_cache=False)
    candidates = catalog.tuning_overrides[1234]
    assert [candidate.name for candidate in candidates] == ["base", "base", "mod"]
    assert [candidate.source.path for candidate in candidates] == [str(base.path), str(repeat.path), str(mod.path)]
    assert candidates[-1].source.resource_key == ResourceKey(hashed, 7, 1234)
    assert catalog.statistics[1234].name == "mod"
    assert catalog.statistics[5678].name == "no_id"
    assert json.loads(catalog.to_json())["tuning_overrides"]["1234"][-1]["source"]["is_mod"]
    static = build_static(installation, packages=packages, strings_packages=[], use_cache=False)
    assert static.catalog.tuning_overrides[1234] == candidates
    retail = build_catalog(installation, packages=[base, repeat], use_cache=False)
    assert retail.tuning_overrides == {}
