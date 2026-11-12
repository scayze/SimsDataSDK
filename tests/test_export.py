"""Serialization (``to_dict`` / ``to_json``) tests."""

from __future__ import annotations

import json
from pathlib import Path

from sims4_sdk import ResourceKey, Sims4JSONEncoder, to_dict, to_json
from sims4_sdk.catalog import (
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    Milestone,
    Preference,
    RelationshipBit,
    Trait,
)
from sims4_sdk.catalog.premades import (
    HouseholdMember,
    HouseholdRelationship,
    PremadeHousehold,
    PremadeLot,
    PremadeSim,
)
from sims4_sdk.catalog.static import StaticData
from sims4_sdk.save.models import (
    SaveFile,
    SavedCareer,
    SavedHousehold,
    SavedMilestone,
    SavedRelationship,
    SavedSim,
    SavedSkill,
    TrayHousehold,
    TrayItem,
    TrayLibrary,
)


def build_catalog() -> Catalog:
    return Catalog(
        traits={
            1: Trait(
                id=1,
                name="trait_Mean",
                display_name="Mean",
                description="Rude.",
                trait_type="PERSONALITY",
            )
        },
        preferences={
            2: Preference(
                id=2,
                name="trait_SimPreference_Likes_HipHop",
                display_name="Likes Hip Hop",
                description=None,
                preference_type="LIKE",
            )
        },
        aspiration_tracks={
            10: AspirationTrack(
                id=10,
                name="Track_Popularity",
                display_name="Popularity",
                description=None,
                aspiration_ids=[11],
            )
        },
        careers={20: Career(id=20, name="career_SecretAgent", start_track_id=21)},
        career_tracks={
            21: CareerTrack(
                id=21,
                name="Career_SecretAgent",
                display_name="Secret Agent",
                description=None,
                level_ids=[22],
            )
        },
        career_levels={
            22: CareerLevel(
                id=22,
                name="career_SecretAgent_Level1",
                title="Intelligence Researcher",
                description=None,
                level=1,
                pay_per_hour=19,
            )
        },
        milestones={
            30: Milestone(
                id=30, name="lifeMilestone_Engaged", display_name="Engaged", description=None
            )
        },
        relationship_bits={
            40: RelationshipBit(
                id=40, name="relbit_Steady", display_name="Steady", description=None
            )
        },
        strings={0x1234: "Hello"},
    ).finalize()


def build_sim() -> PremadeSim:
    catalog = build_catalog()
    return PremadeSim(
        id=100,
        name="template_sim_Bella_Goth",
        first_name="Bella",
        last_name="Goth",
        traits=[catalog.traits[1]],
        preferences=[catalog.preferences[2]],
        aspiration_track_id=10,
        aspiration_track=catalog.aspiration_tracks[10],
        career_level_id=22,
        career_level=catalog.career_levels[22],
        household_id=200,
        household_name="Goth",
        spouse_name="Mortimer Goth",
    )


def test_catalog_to_dict_is_json_safe_and_skips_strings() -> None:
    catalog = build_catalog()
    data = catalog.to_dict()

    assert data["traits"]["1"]["display_name"] == "Mean"
    assert data["traits"]["1"]["is_personality"] is True
    assert data["preferences"]["2"]["preference_type"] == "LIKE"
    assert data["aspiration_tracks"]["10"]["display_name"] == "Popularity"
    assert "strings" not in data
    # Int keys become strings so json.dumps never needs a custom encoder.
    assert list(data["traits"]) == ["1"]
    json.dumps(data)

    with_strings = catalog.to_dict(include_strings=True)
    assert with_strings["strings"]["4660"] == "Hello"


def test_premade_sim_to_dict_includes_computed_fields() -> None:
    sim = build_sim()
    data = sim.to_dict()

    assert data["full_name"] == "Bella Goth"
    assert data["household_name"] == "Goth"
    assert data["career_level"]["title"] == "Intelligence Researcher"
    assert data["aspiration_track"]["display_name"] == "Popularity"
    assert data["traits"][0]["name"] == "trait_Mean"
    assert data["personality_traits"][0]["display_name"] == "Mean"
    assert data["likes"][0]["display_name"] == "Likes Hip Hop"
    assert data["gender_options"]["gender"] is None
    json.dumps(data)


def test_premade_household_and_lot_serialization() -> None:
    household = PremadeHousehold(
        id=200,
        name="Goth",
        funds=9000,
        members=[HouseholdMember(tag="a", sim_template_id=100, full_name="Bella Goth")],
        relationships=[
            HouseholdRelationship(kind="spouse", a_tag="a", b_tag="b", romance=75.0)
        ],
    )
    data = household.to_dict()
    assert data["funds"] == 9000
    assert data["members"][0]["full_name"] == "Bella Goth"
    assert data["relationships"][0]["romance"] == 75.0

    lot = PremadeLot(id=1, lot_name="Ophelia Villa", household_name="Goth", household_id=200)
    assert lot.to_dict()["has_household"] is True


def build_save() -> SaveFile:
    catalog = build_catalog()
    save = SaveFile(path=Path("Slot_00000001.save"))
    save.sims[1] = SavedSim(
        sim_id=1,
        first_name="Bella",
        last_name="Goth",
        household_id=2,
        age="ADULT",
        gender="FEMALE",
        species="HUMAN",
        traits=[catalog.traits[1]],
        preferences=[catalog.preferences[2]],
        aspiration_track=catalog.aspiration_tracks[10],
        careers=[
            SavedCareer(
                career_id=20,
                track_id=21,
                track_level=0,
                career=catalog.careers[20],
                track=catalog.career_tracks[21],
                level=catalog.career_levels[22],
                level_id=22,
            )
        ],
        skills=[SavedSkill(skill_id=55, name="skill_Charisma", value=3.5)],
        relationships=[SavedRelationship(target_id=3, target_name="Mortimer Goth", bits=[40])],
        milestones=[SavedMilestone(milestone_id=30, milestone=catalog.milestones[30])],
        raw={"bytes": b"\x01\x02", "nested": {"x": 1}},
    )
    save.households[2] = SavedHousehold(
        household_id=2, name="Goth", member_ids=[1], members=["Bella Goth"]
    )
    return save


def test_save_to_dict_and_raw_toggle() -> None:
    save = build_save()
    data = save.to_dict()

    sim = data["sims"]["1"]
    assert data["path"] == "Slot_00000001.save"
    assert sim["full_name"] == "Bella Goth"
    assert sim["aspiration_track"]["display_name"] == "Popularity"
    assert sim["careers"][0]["title"] == "Intelligence Researcher"
    assert sim["skills"][0]["value"] == 3.5
    assert "raw" not in sim
    assert data["households"]["2"]["members"] == ["Bella Goth"]
    json.dumps(data)

    with_raw = save.to_dict(include_raw=True)
    assert with_raw["sims"]["1"]["raw"]["bytes"] == "0102"


def test_tray_serialization() -> None:
    item = TrayItem(
        path=Path("0x00000001!0.trayitem"),
        item_id=1,
        title="The Goths",
        hash=b"\xab\xcd",
    )
    household = TrayHousehold(
        path=Path("0x00000001!0.householdbinary"),
        item=item,
        family_name="Goth",
        sims=[SavedSim(sim_id=1, first_name="Bella", last_name="Goth")],
    )
    library = TrayLibrary(items=[item], households=[household])
    data = library.to_dict()
    assert data["items"][0]["hash"] == "abcd"
    assert data["households"][0]["item"]["title"] == "The Goths"
    assert data["households"][0]["sims"][0]["full_name"] == "Bella Goth"
    json.dumps(data)


def test_static_data_and_to_json_round_trip(tmp_path: Path) -> None:
    sim = build_sim()
    static = StaticData(
        catalog=build_catalog(),
        premades=__import__(
            "sims4_sdk.catalog.premades", fromlist=["PremadeBundle"]
        ).PremadeBundle(sims=[sim]),
    )
    target = tmp_path / "static.json"
    text = to_json(static, target, indent=None)

    assert target.read_text(encoding="utf-8") == text
    parsed = json.loads(text)
    assert parsed["catalog"]["traits"]["1"]["name"] == "trait_Mean"
    assert parsed["premades"]["sims"][0]["full_name"] == "Bella Goth"

    tree = static.family_tree("Bella Goth")
    assert tree is not None
    tree_dict = tree.to_dict()
    assert tree_dict["root_id"] == 100
    assert tree_dict["nodes"]["100"]["full_name"] == "Bella Goth"
    json.dumps(tree_dict)


def test_resource_key_bytes_and_path_are_json_safe() -> None:
    key = ResourceKey(0x62E94D38, 0, 0x1234)
    encoder = Sims4JSONEncoder()
    assert encoder.default(key) == "62E94D38!00000000!0000000000001234"
    assert encoder.default(b"\x01\xff") == "01ff"
    assert encoder.default(Path("a/b.save")) == str(Path("a/b.save"))


def test_generic_to_dict_accepts_nested_structures() -> None:
    sim = build_sim()
    data = to_dict({"sim": sim, "keys": [ResourceKey(1, 2, 3)]})
    assert data["sim"]["full_name"] == "Bella Goth"
    assert data["keys"] == ["00000001!00000002!0000000000000003"]


def test_generic_to_dict_propagates_options_to_nested_models() -> None:
    data = to_dict({"catalog": build_catalog()}, include_strings=True)
    assert data["catalog"]["strings"]["4660"] == "Hello"

    plain = to_dict({"catalog": build_catalog()})
    assert "strings" not in plain["catalog"]


def test_generic_to_dict_uses_foreign_to_dict_without_recursing() -> None:
    class Foreign:
        def to_dict(self) -> dict[str, bool]:
            return {"ok": True}

    assert to_dict(Foreign()) == {"ok": True}
    assert to_dict({"foreign": Foreign()}) == {"foreign": {"ok": True}}
