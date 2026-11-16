from copy import deepcopy
from pathlib import Path

from sims4_sdk.save import SaveSource, resolve_save


def test_resolution_preserves_source_and_marks_derived_family():
    source = SaveSource(Path("sample.save"), {
        "sims": [
            {"sim_id": 1, "attributes": {"trait_tracker": {"trait_ids": [12, 34]},
             "genealogy_tracker": {"family_relations": [{"relation_type": 0, "sim_id": 3}]}}},
            {"sim_id": 2, "attributes": {"genealogy_tracker": {
                "family_relations": [{"relation_type": 0, "sim_id": 3}]}}},
            {"sim_id": 3},
        ]
    }, diagnostics=[{"code": "example"}])
    original = deepcopy(source.decoded)

    result = resolve_save(source)
    assert result.sims[1].trait_ids == [12, 34]
    assert result.sims[1].to_dict()["trait_ids"] == [12, 34]
    assert result.sims[1].parents[0].origin == "recorded"
    assert result.sims[1].parents[0].to_dict()["origin"] == "recorded"
    assert result.sims[1].siblings[0].origin == "shared_parent"
    assert result.sims[3].children[0].origin == "reverse_parent"
    result.raw["sims"][0]["attributes"].clear()
    result.diagnostics[0]["code"] = "changed"
    assert source.decoded == original
    assert source.diagnostics == [{"code": "example"}]
    assert source.to_dict()["decoded"]["sims"][0]["sim_id"] == 1
