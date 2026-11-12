"""Integration tests for the save-independent static catalog and pre-made Sims.

The default test builds a representative subset (base game + Growing Together)
so it stays reasonably fast.  Set ``SIMS4_FULL_TEST=1`` to scan every installed
pack; that build can take several minutes and is cached by the SDK.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

from sims4_sdk import Installation
from sims4_sdk.catalog import build_static, load_static
from sims4_sdk.save import read_save, read_tray_library

pytestmark = [pytest.mark.integration, pytest.mark.slow]

BASE_PACKAGES = {
    "SimulationFullBuild0.package",
    "SimulationDeltaBuild0.package",
    "ClientFullBuild0.package",
    "ClientDeltaBuild0.package",
}


def _selected_packages(installation: Installation):
    selected = [
        info
        for info in installation.packages
        if info.pack == "BASE" and info.path.name in BASE_PACKAGES
    ]
    selected.extend(
        info
        for info in installation.packages
        if info.pack == "EP13" and info.path.name == "SimulationDeltaBuild0.package"
    )
    selected.extend(
        info
        for info in installation.packages
        if info.pack == "EP10"
        and info.path.name in {"SimulationDeltaBuild0.package", "ClientDeltaBuild0.package"}
    )
    selected.extend(
        info
        for info in installation.packages
        if info.pack == "EP02"
        and info.path.name in {"SimulationDeltaBuild0.package", "ClientDeltaBuild0.package"}
    )
    return selected


@pytest.fixture(scope="session")
def static_context(install_dir: Path, tmp_path_factory: pytest.TempPathFactory):
    installation = Installation(install_dir)
    selected = _selected_packages(installation)
    cache_dir = tmp_path_factory.mktemp("static-cache")
    data = build_static(
        installation,
        packages=selected,
        use_cache=True,
        cache_dir=cache_dir,
    )
    return installation, selected, cache_dir, data


@pytest.fixture(scope="session")
def static_data(static_context):
    return static_context[3]


def test_catalog_counts(static_data) -> None:
    catalog = static_data.catalog
    assert len(catalog.traits) > 500
    assert len(catalog.preferences) > 100
    assert len(catalog.aspirations) > 100
    assert len(catalog.careers) > 30
    assert len(catalog.career_levels) > 100
    assert len(catalog.milestones) > 50
    assert len(catalog.relationship_bits) > 100
    assert catalog.errors == []


def test_known_trait(static_data) -> None:
    catalog = static_data.catalog
    trait = catalog.trait("trait_Mean")
    assert trait is not None
    assert trait.display_name == "Mean"
    assert trait.trait_type == "PERSONALITY"
    assert "ADULT" in trait.ages
    assert trait.source is not None and trait.source.pack == "BASE"
    assert not trait.is_internal
    assert trait in catalog.visible_traits


def test_known_preference(static_data) -> None:
    catalog = static_data.catalog
    preference = catalog.preference("trait_SimPreference_Likes_Music_HipHop")
    assert preference is not None
    assert preference.display_name == "Likes Hip Hop Music"
    assert preference.preference_type == "LIKE"
    assert preference.is_like


def test_known_aspiration(static_data) -> None:
    catalog = static_data.catalog
    aspiration = catalog.aspiration("aspiration_Fortune_A1")
    assert aspiration is not None
    assert aspiration.display_name == "Going for Not Broke"
    assert aspiration.track_id is not None
    track = catalog.aspiration_tracks.get(aspiration.track_id)
    assert track is not None
    assert aspiration.id in track.aspiration_ids


def test_known_career_level(static_data) -> None:
    catalog = static_data.catalog
    level = catalog.career_level("career_SecretAgent_Villain_Level3")
    assert level is not None
    assert level.title == "Supreme Villain"
    assert level.level == 3
    assert level.pay_per_hour == 479
    assert "SUNDAY" in level.work_days


def test_milestones(static_data) -> None:
    catalog = static_data.catalog
    milestone = catalog.milestone("lifeMilestone_Engaged")
    assert milestone is not None
    assert milestone.display_name == "Got Engaged"
    assert milestone.category == "Social"
    assert milestone.repeatable is True
    assert "ADULT" in milestone.ages


def test_premade_goths(static_data) -> None:
    data = static_data
    bella = data.sim("Bella Goth")
    assert bella is not None
    assert bella.first_name == "Bella"
    assert bella.last_name == "Goth"
    assert bella.household_name == "premadeHouseholdTemplate_Goth"
    assert "trait_FamilyOriented" in bella.trait_names
    assert "Trait_Romantic" in bella.trait_names

    household = data.household("premadeHouseholdTemplate_Goth")
    assert household is not None
    assert len(household.members) == 4
    names = {member.full_name for member in household.members}
    assert {"Mortimer Goth", "Bella Goth", "Cassandra Goth", "Alexander Goth"} <= names

    kinds = {(rel.kind, rel.family_relationship) for rel in household.relationships}
    assert ("spouse", None) in kinds
    assert ("family", "FATHER") in kinds
    assert ("family", "MOTHER") in kinds


def test_premade_ancestors(static_data) -> None:
    names = {ancestor.full_name for ancestor in static_data.ancestors}
    assert "Cornelia Goth" in names
    assert "Darren Dreamer" in names

    cornelia = static_data.ancestor("Cornelia Goth")
    assert cornelia is not None
    assert "Mortimer Goth" in cornelia.children
    assert {"Prudence Crumplebottom", "Simon Crumplebottom"} <= set(cornelia.parents)

    tree = static_data.family_tree("Cassandra Goth")
    assert tree is not None
    ancestor_names = {node.full_name for node in tree.ancestors_of()}
    assert {
        "Bella Goth",
        "Mortimer Goth",
        "Cornelia Goth",
        "Prudence Crumplebottom",
        "Simon Crumplebottom",
    } <= ancestor_names


def test_starter_save_household_bff(static_data) -> None:
    """The BFF household has no tuning template at all; it lives in 0xB3C438F0."""
    household = static_data.household("BFF")
    assert household is not None
    assert household.funds == 9000
    assert {member.full_name for member in household.members} == {
        "Travis Scott",
        "Liberty Lee",
        "Summer Holiday",
    }

    liberty = static_data.sim("Liberty Lee")
    assert liberty is not None
    assert liberty.household_name == "BFF"
    assert liberty.gender == "FEMALE"
    assert liberty.age == "YOUNGADULT"
    assert {trait.display_name for trait in liberty.personality_traits} == {
        "Geek",
        "Bookworm",
        "Clumsy",
    }
    assert liberty.aspiration_track is not None
    assert liberty.aspiration_track.display_name == "Nerd Brain"
    assert liberty.career is not None
    assert liberty.career_level is not None
    assert liberty.career_level.title == "Module Cleaner"
    assert liberty.career_track_level == 1
    assert liberty.career_display_level == 2
    assert liberty.skills
    assert any(skill.value and skill.value > 100 for skill in liberty.skills)


def test_starter_save_other_base_households(static_data) -> None:
    for name, funds in (("Pancakes", 20000), ("Roomies", 14000), ("Spencer-Kim-Lewis", 55500)):
        household = static_data.household(name)
        assert household is not None, name
        assert household.funds == funds
        assert household.members

    assert static_data.sim("Bob Pancakes") is not None
    assert static_data.sim("Zoe Patel") is not None
    assert static_data.sim("Dennis Kim") is not None


def test_starter_hints_enrich_tuning_households(static_data) -> None:
    """Goth/Landgraab/Zest exist in tuning; the resource only adds funds/hints."""
    goth = static_data.household("premadeHouseholdTemplate_Goth")
    assert goth is not None
    assert goth.funds == 45500

    # The resource's own household name is registered as an alias.
    assert static_data.household("Goth") is goth
    assert static_data.household("Landgraab") is not None

    bella = static_data.sim("Bella Goth")
    assert bella is not None
    assert bella.gender == "FEMALE"
    assert bella.career_level is not None
    assert bella.career_level.title == "Intelligence Researcher"


def test_starter_save_genealogy(static_data) -> None:
    bob = static_data.sim("Bob Pancakes")
    eliza = static_data.sim("Eliza Pancakes")
    assert bob.spouse_name == "Eliza Pancakes"
    assert eliza.spouse_name == "Bob Pancakes"
    pancakes = static_data.household("Pancakes")
    assert ("spouse", None) in {
        (rel.kind, rel.family_relationship) for rel in pancakes.relationships
    }

    dina = static_data.sim("Dina Caliente")
    nina = static_data.sim("Nina Caliente")
    katrina = static_data.sim("Katrina Caliente")
    assert dina.parents == ["Katrina Caliente"]
    assert nina.parents == ["Katrina Caliente"]
    assert "Dina Caliente" in katrina.children
    assert "Nina Caliente" in katrina.children
    assert "Nina Caliente" in dina.siblings
    assert "Dina Caliente" in nina.siblings

    olivia = static_data.sim("Olivia Spencer-Kim")
    assert {"Alice Spencer-Kim", "Eric Lewis"} <= set(olivia.parents)
    assert {"Dennis Kim", "Vivian Lewis"} <= set(olivia.extended_family)

    # Goth uses tuning for the household relationships, but the starter
    # resource still supplies the Sim-level family fields.
    bella = static_data.sim("Bella Goth")
    cassandra = static_data.sim("Cassandra Goth")
    assert bella.spouse_name == "Mortimer Goth"
    assert {"Bella Goth", "Mortimer Goth"} <= set(cassandra.parents)
    assert "Alexander Goth" in cassandra.siblings

    candy = static_data.sim("Candy Behr")
    yuki = static_data.sim("Yuki Behr")
    assert "Yuki Behr" in candy.siblings
    assert "Candy Behr" in yuki.siblings

    johnny = static_data.sim("Johnny Zest")
    assert {"Geoffrey Landgraab", "Nancy Landgraab"} <= set(johnny.parents)
    assert "Malcolm Landgraab" in johnny.siblings


def test_ep10_household_uses_positional_hints(static_data) -> None:
    """EP10 household resources have unnamed members; match them by position."""
    megumi = static_data.sim("Megumi Ito")
    assert megumi is not None
    assert megumi.household_name == "premadeHouseholdTemplate_EP10_Affluent"
    assert megumi.age == "YOUNGADULT"
    assert megumi.gender == "FEMALE"
    assert megumi.spouse_name == "Naoki Ito"
    assert {"Kiyoshi Ito", "Nanami Ito"} <= set(megumi.children)
    assert megumi.career is not None
    assert megumi.career.name == "career_Adult_Business"
    assert megumi.career_track is not None
    assert megumi.career_track.display_name == "Business"
    assert megumi.career_level is not None
    assert megumi.career_level.title == "Senior Manager"

    household = static_data.household("premadeHouseholdTemplate_EP10_Affluent")
    assert household is not None
    assert household.funds == 40000
    lot = static_data.lot("2-5-1 Wakabamori")
    assert lot is not None
    assert lot.household_name == "Ito"
    assert lot.household_id == household.id


def test_relationship_defaults_and_values(static_data) -> None:
    catalog = static_data.catalog

    family = catalog.relationship_defaults["FamilyMember"].track(16650)
    spouse = catalog.relationship_defaults["Spouse"].track(16651)
    roommate = catalog.relationship_defaults["Roommate"].track(16650)
    assert (family.value, spouse.value, roommate.value) == (45, 75, 15)

    pancakes = static_data.household("Pancakes")
    pancakes_spouse = next(
        rel for rel in pancakes.relationships if rel.kind == "spouse"
    )
    assert (pancakes_spouse.friendship, pancakes_spouse.romance) == (45, 75)

    caliente = static_data.household("Caliente")
    mother = next(
        rel
        for rel in caliente.relationships
        if rel.kind == "family" and rel.family_relationship == "MOTHER"
    )
    assert (mother.friendship, mother.romance) == (45, 0)

    megumi = static_data.sim("Megumi Ito")
    kado = static_data.sim("Kado Akiyama")
    sachiko = static_data.sim("Sachiko Nishidake")
    kado_rel = static_data.premades.relationship(megumi.id, kado.id)
    sachiko_rel = static_data.premades.relationship(megumi.id, sachiko.id)
    assert kado_rel is not None and sachiko_rel is not None
    assert (kado_rel.friendship, kado_rel.romance) == (10, -60)
    assert sachiko_rel.friendship == 60
    assert sachiko_rel.romance is None


def test_global_relationship_tuning(static_data) -> None:
    catalog = static_data.catalog

    assert catalog.steady_bit_id == 15825
    assert catalog.engagement_bit_id == 15816
    assert catalog.marriage_bit_id == 15822
    assert set(catalog.family_trope_ids) == {
        306293,
        306291,
        306294,
        310888,
        306282,
        306279,
        306356,
        306357,
        306289,
        306296,
    }
    assert set(catalog.romance_trope_ids) == {362476, 362478, 362477, 362475}
    assert catalog.is_family_trope(306293)
    assert catalog.is_romance_trope(362476)
    assert not catalog.is_family_trope(362476)


def test_premade_gender_options(static_data) -> None:
    mortimer = static_data.sim("Mortimer Goth")
    assert mortimer is not None

    options = mortimer.gender_options
    assert options.frame == "MASCULINE"
    assert options.clothing == "MENSWEAR"
    assert options.toilet_use == "STANDING"
    assert options.can_impregnate is True
    assert options.can_be_impregnated is False


def test_relationship_track_ranges(static_data) -> None:
    catalog = static_data.catalog

    lovebirds = catalog.relationship_track_ranges[15829]
    assert (lovebirds.min_value, lovebirds.max_value) == (25, 75)
    complicated = catalog.relationship_track_ranges[15834]
    assert (complicated.min_value, complicated.max_value) == (-50, -10)

    bjergsen = static_data.household("HH_Template_Bjergsen")
    spouse = next(rel for rel in bjergsen.relationships if rel.kind == "spouse")
    assert (spouse.romance_min, spouse.romance_max) == (25, 75)

    partihaus = static_data.household("HH_Template_Partihaus")
    relation = next(
        rel for rel in partihaus.relationships if 15834 in rel.bit_ids
    )
    assert (relation.romance_min, relation.romance_max) == (-50, -10)


def test_lot_manifest(static_data) -> None:
    lots = static_data.lots
    assert lots

    garden = static_data.lot("Garden Essence")
    assert garden is not None
    assert garden.household_name == "BFF"
    assert garden.household_id == static_data.household("BFF").id
    assert garden.lot_description
    source_lot = static_data.world.lots[garden.id]
    source_household = static_data.world.households[source_lot.household_id]
    assert source_lot.raw and source_household.raw
    assert source_household.source.path and source_household.source.resource_key
    assert source_household.source.resource_key.instance == source_household.instance
    assert static_data.world.household_resources[source_household.source.resource_key] is source_household
    assert static_data.world.lot_resources[source_lot.source.resource_key] is source_lot
    assert source_household.members
    member = source_household.members[0]
    if member.sim_id is not None:
        assert (source_household, member) in static_data.world.find_members(member.sim_id)
    bff = static_data.household("BFF")
    assert bff.localized_name == garden.household_name
    assert bff.display_name == garden.household_name
    assert bff.description == garden.household_description
    assert garden.id in bff.lot_ids
    assert static_data.find_households("BFF")

    ophelia = static_data.lot("Ophelia Villa")
    assert ophelia is not None
    assert ophelia.household_name == "Goth"
    assert ophelia.household_id == static_data.household("premadeHouseholdTemplate_Goth").id


def test_cache_roundtrip(static_context) -> None:
    installation, selected, cache_dir, data = static_context
    cached = load_static(installation, packages=selected, cache_dir=cache_dir)
    assert cached is not None
    assert len(cached.catalog.traits) == len(data.catalog.traits)
    assert len(cached.premades.sims) == len(data.premades.sims)


def test_save_file(static_data, user_dir: Path) -> None:
    saves = sorted((Path(user_dir) / "saves").glob("*.save"))
    if not saves:
        pytest.skip("no save files in the user directory")

    save = read_save(saves[0], static_data.catalog)
    assert save.slot.slot_name
    assert save.sims
    assert save.households
    assert save.zones

    bella = save.sim("Bella Goth")
    if bella is None:
        pytest.skip("the save does not contain Bella Goth")

    assert bella.age in {"BABY", "TODDLER", "CHILD", "TEEN", "YOUNGADULT", "ADULT", "ELDER"}
    assert bella.gender in {"MALE", "FEMALE"}
    assert bella.species == "HUMAN"
    assert bella.personality_traits
    assert bella.career is not None
    assert bella.spouse_id is not None
    assert bella.children
    assert bella.household_name


def test_tray_library(static_data, user_dir: Path) -> None:
    tray_dir = Path(user_dir) / "Tray"
    if not tray_dir.is_dir():
        pytest.skip("no Tray folder in the user directory")

    library = read_tray_library(tray_dir, static_data.catalog)
    assert library.households
    assert library.items
    household = next((hh for hh in library.households if hh.sims), None)
    assert household is not None
    assert household.family_name
    assert household.sims[0].full_name
    files = {str(path) for path in tray_dir.glob("*.householdbinary")}
    decoded = {str(hh.path) for hh in library.households}
    failed = {error["path"] for error in library.errors} & files
    assert decoded.isdisjoint(failed)
    assert decoded | failed == files
    print(f"Tray household files: {len(files)}, decoded: {len(decoded)}, reported errors: {len(failed)}")


@pytest.mark.skipif(
    os.environ.get("SIMS4_FULL_TEST") != "1",
    reason="set SIMS4_FULL_TEST=1 to scan every installed pack",
)
def test_full_installation(install_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    installation = Installation(install_dir)
    cache_dir = tmp_path_factory.mktemp("full-static-cache")
    data = build_static(installation, use_cache=True, cache_dir=cache_dir)

    print(
        f"Full install: {len(installation.packages)} packages, "
        f"{len(data.catalog.traits)} traits, {len(data.catalog.visible_traits)} in visible view, "
        f"{len(data.premades.households)} households, "
        f"{sum(bool(hh.lot_ids) for hh in data.premades.households)} with lot links, "
        f"{len(data.catalog.errors)} catalog errors, "
        f"diagnostics: {dict(Counter(issue.stage for issue in data.catalog.diagnostics))}"
    )

    assert len(data.catalog.traits) > 900
    assert len(data.catalog.preferences) > 150
    assert len(data.catalog.milestones) > 100
    assert len(data.premades.sims) > 100
    assert len(data.premades.households) > 50
