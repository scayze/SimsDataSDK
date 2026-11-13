"""Coverage information for unsupported save persistence resources."""

from conftest import build_package
from sims4_sdk import ResourceKey
from sims4_sdk.save import read_save, read_save_resource


def test_persistence_resources_report_potentially_incomplete_relationships(tmp_path):
    path = tmp_path / "sample.save"
    path.write_bytes(build_package([
        {"type": 13, "group": 0, "instance": 1, "data": b"\x00"},
        {"type": 6, "group": 2, "instance": 3, "data": b"opaque"},
        {"type": 6, "group": 4, "instance": 5, "data": b"opaque"},
    ]))

    save = read_save(path)
    assert save.relationship_coverage == "potentially_incomplete"
    assert len(save.diagnostics) == 2
    assert {item["resource_key"] for item in save.diagnostics} == {
        str(ResourceKey(6, 2, 3)), str(ResourceKey(6, 4, 5))
    }
    assert all(item["recoverable"] is True for item in save.diagnostics)
    assert all("may contain" in item["message"] for item in save.diagnostics)
    assert save.to_dict()["diagnostics"] == save.diagnostics
    assert save.to_dict()["relationship_coverage"] == "potentially_incomplete"


def test_absence_of_persistence_resources_does_not_claim_completeness(tmp_path):
    path = tmp_path / "sample.save"
    path.write_bytes(build_package([
        {"type": 13, "group": 0, "instance": 1, "data": b"\x00"},
    ]))
    assert read_save(path).relationship_coverage == "unknown"
    assert read_save_resource(b"\x00").relationship_coverage == "unknown"
    assert read_save(path).diagnostics == []
