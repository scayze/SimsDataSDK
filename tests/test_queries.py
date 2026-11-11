"""Lookup and filtering tests for catalogs, pre-mades, saves, and Tray data."""

from __future__ import annotations

from pathlib import Path

from sims4_sdk.catalog import (
    Aspiration,
    AspirationCategory,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    Milestone,
    Preference,
    RelationshipBit,
    Trait,
    TuningSource,
)
from sims4_sdk.catalog.premades import (
    HouseholdMember,
    PremadeBundle,
    PremadeHousehold,
    PremadeLot,
    PremadeSim,
)
from sims4_sdk.catalog.static import StaticData
from sims4_sdk.save.models import (
    SaveFile,
    SavedHousehold,
    SavedSim,
    TrayHousehold,
    TrayItem,
    TrayLibrary,
)

BASE = TuningSource(package="Data/Client/Base.package", pack="BASE")
EP01 = TuningSource(package="EP01/ClientDeltaBuild0.package", pack="EP01")


def build_catalog() -> Catalog:
    return Catalog(
        traits={
            1: Trait(
                id=1,
                name="trait_Mean",
                display_name="Mean",
                description=None,
                trait_type="PERSONALITY",
                source=BASE,
            ),
            2: Trait(
                id=2,
                name="trait_Cheerful",
                display_name="Cheerful",
                description=None,
                trait_type="PERSONALITY",
                source=BASE,
            ),
            3: Trait(
                id=3,
                name="trait_Occult_Vampire",
                display_name="Vampire",
                description=None,
                trait_type="OCCULT",
                is_hidden=True,
                source=EP01,
            ),
        },
        preferences={
            10: Preference(
                id=10,
                name="trait_Likes_Cooking",
                display_name="Likes Cooking",
                description=None,
                preference_type="LIKE",
                source=BASE,
            ),
            11: Preference(
                id=11,
                name="trait_Dislikes_Fitness",
                display_name="Dislikes Fitness",
                description=None,
                preference_type="DISLIKE",
                source=EP01,
            ),
        },
        aspiration_categories={
            20: AspirationCategory(
                id=20, name="AspirationCategory_Deviance", display_name="Deviance"
            )
        },
        aspiration_tracks={
            21: AspirationTrack(
                id=21,
                name="AspirationTrack_PublicEnemy",
                display_name="Public Enemy",
                description=None,
                category_id=20,
                source=EP01,
            )
        },
        aspirations={
            22: Aspiration(
                id=22,
                name="Aspiration_PublicEnemy",
                display_name="Public Enemy",
                description=None,
                track_id=21,
                source=EP01,
            )
        },
        careers={
            30: Career(id=30, name="career_Criminal", start_track_id=31, source=BASE)
        },
        career_tracks={
            31: CareerTrack(
                id=31,
                name="Career_Criminal",
                display_name="Criminal",
                description=None,
                level_ids=[32],
                source=BASE,
            )
        },
        career_levels={
            32: CareerLevel(
                id=32,
                name="career_Criminal_Level1",
                title="Ringleader",
                description=None,
                level=1,
                pay_per_hour=25,
                source=BASE,
            )
        },
        milestones={
            40: Milestone(
                id=40,
                name="milestone_FirstKiss",
                display_name="First Kiss",
                description=None,
                category="ROMANCE",
                source=BASE,
            ),
            41: Milestone(
                id=41,
                name="milestone_Promotion",
                display_name="Promotion",
                description=None,
                category="CAREER",
                source=EP01,
            ),
        },
        relationship_bits={
            50: RelationshipBit(
                id=50,
                name="relbit_Acquaintance",
                display_name="Acquaintance",
                description=None,
                source=BASE,
            )
        },
        tuning_names={60: "skill_Cooking", 61: "statistic_Fun"},
        tuning_classes={60: "Skill", 61: "Statistic"},
    ).finalize()


def build_bundle() -> PremadeBundle:
    sims = [
        PremadeSim(
            id=100,
            name="template_sim_Bella_Goth",
            first_name="Bella",
            last_name="Goth",
            household_id=200,
            household_name="Goth",
            age_hint="ADULT",
            occult_type=None,
            source=BASE,
        ),
        PremadeSim(
            id=101,
            name="template_sim_Mortimer_Goth",
            first_name="Mortimer",
            last_name="Goth",
            household_id=200,
            household_name="Goth",
            age_hint="ADULT",
            source=BASE,
        ),
        PremadeSim(
            id=102,
            name="template_sim_Lily_Feng",
            first_name="Lily",
            last_name="Feng",
            household_id=201,
            household_name="Feng",
            age_hint="YOUNGADULT",
            occult_type="VAMPIRE",
            source=EP01,
        ),
    ]
    households = [
        PremadeHousehold(id=200, name="Goth", source=BASE),
        PremadeHousehold(id=201, name="Feng", source=EP01),
    ]
    lots = [
        PremadeLot(
            id=300,
            lot_name="Ophelia Villa",
            household_name="Goth",
            household_id=200,
            source=BASE,
        ),
        PremadeLot(id=301, lot_name="Empty Lot", source=BASE),
    ]
    return PremadeBundle(sims=sims, households=households, lots=lots)


def build_save() -> SaveFile:
    save = SaveFile(path=Path("Slot_00000001.save"))
    save.sims[1] = SavedSim(
        sim_id=1,
        first_name="Bella",
        last_name="Goth",
        household_id=2,
        household_name="Goth",
        age="ADULT",
        species="HUMAN",
        occult=["VAMPIRE"],
    )
    save.sims[2] = SavedSim(
        sim_id=2,
        first_name="Mortimer",
        last_name="Goth",
        household_id=2,
        household_name="Goth",
        age="ADULT",
        species="HUMAN",
    )
    save.sims[3] = SavedSim(
        sim_id=3,
        first_name="Bella",
        last_name="Bachelor",
        household_id=3,
        household_name="Bachelor",
        age="YOUNGADULT",
        species="HUMAN",
        death={"death_type": 1},
    )
    save.households[2] = SavedHousehold(
        household_id=2, name="Goth", member_ids=[1, 2], is_player=True
    )
    save.households[3] = SavedHousehold(
        household_id=3, name="Bachelor", member_ids=[3], is_player=False
    )
    save.slot.active_household_id = 2
    return save


# ----------------------------------------------------------------------
# catalog
# ----------------------------------------------------------------------
def test_catalog_name_lookups_are_exact_then_case_insensitive() -> None:
    catalog = build_catalog()

    assert catalog.trait("trait_Mean") is catalog.traits[1]
    assert catalog.trait("TRAIT_MEAN") is catalog.traits[1]
    assert catalog.trait("trait_missing") is None
    assert catalog.trait(1) is catalog.traits[1]
    assert catalog.trait(999) is None

    assert catalog.preference("trait_likes_cooking") is catalog.preferences[10]
    assert catalog.aspiration("ASPIRATION_PUBLICENEMY") is catalog.aspirations[22]
    assert catalog.aspiration_track("aspirationtrack_publicenemy").id == 21
    assert catalog.aspiration_category("aspirationcategory_deviance").id == 20
    assert catalog.career("CAREER_CRIMINAL").id == 30
    assert catalog.career_track("career_criminal").id == 31
    assert catalog.career_level("career_criminal_level1").id == 32
    assert catalog.milestone("MILESTONE_FIRSTKISS").id == 40
    assert catalog.relationship_bit("RELBIT_ACQUAINTANCE").id == 50


def test_tuning_name_and_class_lookup() -> None:
    catalog = build_catalog()
    assert catalog.tuning_name(60) == "skill_Cooking"
    assert catalog.tuning_class(60) == "Skill"
    assert catalog.tuning_name(999) is None
    assert catalog.tuning_class(999) is None


def test_find_traits_filters() -> None:
    catalog = build_catalog()

    assert [trait.id for trait in catalog.find_traits("mean")] == [1]
    assert [trait.id for trait in catalog.find_traits("CHEER")] == [2]
    assert {trait.id for trait in catalog.find_traits()} == {1, 2, 3}

    personality = catalog.find_traits(trait_type="personality")
    assert {trait.id for trait in personality} == {1, 2}

    ep01 = catalog.find_traits(pack="EP01")
    assert [trait.id for trait in ep01] == [3]

    visible = catalog.find_traits(visible_only=True)
    assert {trait.id for trait in visible} == {1, 2}
    assert [trait.id for trait in catalog.find_traits("vampire", visible_only=True)] == []


def test_find_preferences_aspirations_careers_milestones() -> None:
    catalog = build_catalog()

    assert [item.id for item in catalog.find_preferences("cooking")] == [10]
    assert [item.id for item in catalog.find_preferences(preference_type="dislike")] == [11]
    assert [item.id for item in catalog.find_preferences(pack="base")] == [10]

    assert [item.id for item in catalog.find_aspirations("public")] == [22]
    assert [item.id for item in catalog.find_aspirations(pack="EP01")] == [22]

    assert [item.id for item in catalog.find_careers("criminal")] == [30]
    assert [item.id for item in catalog.find_careers(pack="EP01")] == []

    assert {item.id for item in catalog.find_milestones("kiss")} == {40}
    assert [item.id for item in catalog.find_milestones(category="career")] == [41]
    assert [item.id for item in catalog.find_milestones(pack="BASE")] == [40]


def test_catalog_packs() -> None:
    assert build_catalog().packs() == ["BASE", "EP01"]


# ----------------------------------------------------------------------
# pre-mades
# ----------------------------------------------------------------------
def test_premade_lookups_accept_ids_names_and_fragments() -> None:
    bundle = build_bundle()

    assert bundle.sim(100).full_name == "Bella Goth"
    assert bundle.sim("Bella Goth").full_name == "Bella Goth"
    assert bundle.sim("BELLA GOTH").full_name == "Bella Goth"
    assert bundle.sim("goth").id == 100
    assert bundle.sim("missing") is None

    assert bundle.household(200).name == "Goth"
    assert bundle.household("goth").name == "Goth"
    assert bundle.household("fen").name == "Feng"

    assert bundle.lot(300).lot_name == "Ophelia Villa"
    assert bundle.lot("ophelia").id == 300
    assert bundle.lot("no such lot") is None


def test_premade_sim_filters() -> None:
    bundle = build_bundle()

    assert {sim.id for sim in bundle.find_sims("goth")} == {100, 101}
    assert [sim.id for sim in bundle.find_sims(household="Feng")] == [102]
    assert [sim.id for sim in bundle.find_sims(household=200)] == [100, 101]
    assert [sim.id for sim in bundle.find_sims(age="youngadult")] == [102]
    assert [sim.id for sim in bundle.find_sims(occult="vampire")] == [102]
    assert [sim.id for sim in bundle.find_sims(pack="EP01")] == [102]
    assert bundle.find_sims("nobody") == []


def test_premade_household_and_lot_filters() -> None:
    bundle = build_bundle()

    assert [item.id for item in bundle.find_households("go")] == [200]
    assert [item.id for item in bundle.find_households(pack="EP01")] == [201]

    assert [item.id for item in bundle.find_lots("ophelia")] == [300]
    assert [item.id for item in bundle.find_lots("goth")] == [300]
    assert [item.id for item in bundle.find_lots(occupied_only=True)] == [300]
    assert [item.id for item in bundle.find_lots(pack="EP01")] == []


def test_static_data_delegates_lookups() -> None:
    static = StaticData(catalog=build_catalog(), premades=build_bundle())

    assert static.sim("bella").id == 100
    assert static.household("GOTH").id == 200
    assert static.lot("ophelia").id == 300
    assert [sim.id for sim in static.find_sims(age="ADULT")] == [100, 101]
    assert [item.id for item in static.find_households("feng")] == [201]
    assert [item.id for item in static.find_lots(occupied_only=True)] == [300]


# ----------------------------------------------------------------------
# saves
# ----------------------------------------------------------------------
def test_save_sim_lookup_prefers_exact_names() -> None:
    save = build_save()

    assert save.sim(1).first_name == "Bella"
    assert save.sim("Bella Goth").last_name == "Goth"
    assert save.sim("BELLA GOTH").last_name == "Goth"
    assert save.sim("bella").last_name == "Goth"  # first fragment match wins
    assert save.sim("nobody") is None


def test_save_household_lookup_and_members() -> None:
    save = build_save()

    assert save.household(2).name == "Goth"
    assert save.household("GOTH").name == "Goth"
    assert save.household("bach").name == "Bachelor"
    assert save.active_household is save.households[2]
    assert [sim.sim_id for sim in save.household_sims(2)] == [1, 2]
    assert [sim.sim_id for sim in save.household_sims("Goth")] == [1, 2]
    assert save.household_sims(999) == []


def test_save_find_sims_filters() -> None:
    save = build_save()

    assert {sim.sim_id for sim in save.find_sims("bella")} == {1, 3}
    assert [sim.sim_id for sim in save.find_sims(household=2)] == [1, 2]
    assert [sim.sim_id for sim in save.find_sims(household="Bachelor")] == [3]
    assert [sim.sim_id for sim in save.find_sims(age="adult")] == [1, 2]
    assert [sim.sim_id for sim in save.find_sims(occult="vampire")] == [1]
    assert [sim.sim_id for sim in save.find_sims(is_dead=True)] == [3]
    assert [sim.sim_id for sim in save.find_sims(occult="VAMPIRE", is_dead=False)] == [1]
    assert save.find_sims("nobody") == []


def test_save_find_households_filters() -> None:
    save = build_save()

    assert [hh.household_id for hh in save.find_households()] == [2, 3]
    assert [hh.household_id for hh in save.find_households("go")] == [2]
    assert [hh.household_id for hh in save.find_households(is_player=True)] == [2]
    assert [hh.household_id for hh in save.find_households(is_player=False)] == [3]


# ----------------------------------------------------------------------
# Tray
# ----------------------------------------------------------------------
def build_tray() -> TrayLibrary:
    goth_item = TrayItem(
        path=Path("0x00000001!0.trayitem"),
        item_id=1,
        title="The Goths",
        creator="Maxis",
    )
    feng_item = TrayItem(
        path=Path("0x00000002!0.trayitem"),
        item_id=2,
        title="Feng Family",
        creator="SomeoneElse",
    )
    return TrayLibrary(
        items=[goth_item, feng_item],
        households=[
            TrayHousehold(
                path=Path("0x00000001!0.householdbinary"),
                item=goth_item,
                family_name="Goth",
                sims=[SavedSim(sim_id=1, first_name="Bella", last_name="Goth")],
            ),
            TrayHousehold(
                path=Path("0x00000002!0.householdbinary"),
                item=feng_item,
                family_name="Feng",
                sims=[SavedSim(sim_id=2, first_name="Lily", last_name="Feng")],
            ),
        ],
    )


def test_tray_household_lookup_exact_then_fragment() -> None:
    tray = build_tray()

    assert tray.household(1).family_name == "Goth"
    assert tray.household("Goth").family_name == "Goth"
    assert tray.household("the goths").family_name == "Goth"
    assert tray.household("fen").family_name == "Feng"
    assert tray.household("nobody") is None


def test_tray_filters() -> None:
    tray = build_tray()

    assert [hh.family_name for hh in tray.find_households("go")] == ["Goth"]
    assert [hh.family_name for hh in tray.find_households(creator="maxis")] == ["Goth"]
    assert [hh.family_name for hh in tray.find_households(creator="Nobody")] == []
    assert [sim.first_name for sim in tray.find_sims("lily")] == ["Lily"]
    assert len(tray.find_sims()) == 2
