import json

from conftest import build_package
from test_artwork import jpeg
from sims4_sdk.core import ResourceKey
from sims4_sdk.installation import PackageInfo
from sims4_sdk.premade_artwork import PREMADE_COMPOSITE_TYPE, PremadeCompositeIndex


def test_composites_use_full_key_precedence_and_keep_partial_results(tmp_path):
    def resource(group, instance, data):
        return {"type": PREMADE_COMPOSITE_TYPE, "group": group,
                "instance": instance, "data": data}

    base, mod = tmp_path / "base.package", tmp_path / "mod.package"
    base.write_bytes(build_package([
        resource(1, 42, jpeg(width=10, height=10)),
        resource(2, 42, jpeg(width=30, height=20)),
        resource(3, 42, jpeg()),
    ]))
    mod.write_bytes(build_package([
        resource(1, 42, jpeg(width=40, height=20)),
        resource(3, 42, b"bad"),
    ]))

    class InstallationFixture:
        packages = [PackageInfo(base, "BASE"), PackageInfo(mod, "MOD", True),
                    PackageInfo(tmp_path / "missing.package", "BASE")]

    index = PremadeCompositeIndex(InstallationFixture())
    result = index.read([42, 999])
    assert len(result.images) == 2
    assert result.largest(42).key == ResourceKey(PREMADE_COMPOSITE_TYPE, 1, 42)
    assert result.largest(42).package.path == mod
    assert result.largest(42).artwork.alpha_mask is not None
    assert json.loads(result.to_json())["images"][0]["package_path"]
    assert result.largest(999) is None
    assert {issue.stage for issue in result.diagnostics} == {"composite_index", "composite_read"}
    assert next(issue for issue in result.diagnostics if issue.stage == "composite_read").resource_key.group == 3
