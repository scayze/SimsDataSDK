from sims4_sdk.catalog import (
    Catalog,
    LotRecord,
    Preference,
    StarterHouseholdRecord,
    StarterMember,
    PremadeSim,
    SkillLevel,
    Trait,
    WorldData,
    build_premades,
    parse_resource_key,
)
from sims4_sdk.core import CombinedTuning


def test_parse_resource_key() -> None:
    key = parse_resource_key("025ed6f4:00000000:7954cdc9ba5dba03")
    assert key is not None
    assert key.type_id == 0x025ED6F4
    assert key.group == 0
    assert key.instance == 0x7954CDC9BA5DBA03
    assert parse_resource_key("nope") is None
    assert parse_resource_key(None) is None


def test_premade_sim_properties() -> None:
    trait = Trait(
        id=1,
        name="trait_Romantic",
        display_name="Romantic",
        description=None,
        trait_type="PERSONALITY",
    )
    hidden = Trait(
        id=2,
        name="trait_WalkStyleFeminine",
        display_name="Feminine",
        description=None,
        trait_type="WALKSTYLE",
    )
    preference = Preference(
        id=3,
        name="trait_SimPreference_Likes_Cooking",
        display_name="Likes Cooking",
        description=None,
        preference_type="LIKE",
    )
    sim = PremadeSim(
        id=10,
        name="premadeSimTemplate_Test",
        first_name="Bella",
        last_name="Goth",
        traits=[trait, hidden],
        preferences=[preference],
        skills=[SkillLevel(skill_id=5, level=3)],
    )

    assert sim.full_name == "Bella Goth"
    assert sim.trait_names == ["trait_Romantic", "trait_WalkStyleFeminine"]
    assert sim.personality_traits == [trait]
    assert sim.hidden_traits == []
    assert sim.visible_traits == [trait]
    assert sim.preference_names == ["trait_SimPreference_Likes_Cooking"]
    assert sim.likes == [preference]
    assert sim.dislikes == []


def test_premade_sim_derived_species_gender_occult() -> None:
    def trait(name: str, type_: str = "HIDDEN") -> Trait:
        return Trait(
            id=hash(name) & 0xFFFFFFFF,
            name=name,
            display_name=name,
            description=None,
            trait_type=type_,
        )

    sim = PremadeSim(
        id=1,
        name="premadeSimTemplate_Pet",
        first_name="Rex",
        last_name="",
        traits=[
            trait("trait_Species_Dog"),
            trait("trait_GenderMale"),
            trait("trait_Occult_NoOccult"),
        ],
    )
    assert sim.species == "Dog"
    assert sim.gender == "MALE"
    assert sim.occult == "NoOccult"


def test_premade_sim_gender_options() -> None:
    def trait(name: str, type_: str = "GENDER_OPTIONS") -> Trait:
        return Trait(
            id=abs(hash(name)) & 0xFFFFFFFF,
            name=name,
            display_name=name,
            description=None,
            trait_type=type_,
        )

    sim = PremadeSim(
        id=1,
        name="premadeSimTemplate_Test",
        first_name="Alex",
        last_name="Test",
        traits=[
            trait("trait_GenderOptions_Frame_Feminine"),
            trait("trait_GenderOptions_Clothing_WomensWear"),
            trait("trait_GenderOptions_Toilet_Sitting"),
            trait("trait_GenderOptions_Lactate_CanNot"),
            trait("trait_GenderOptions_AttractedTo_Male"),
            trait("trait_GenderOptions_AttractedTo_Female"),
            trait("trait_GenderOptions_AttractedTo_NotMale"),
            trait("trait_SexualOrientation_WooHooInterests_Female"),
            trait("trait_GenderOptions_Sexuality_Exploring"),
            trait("trait_GenderOptions_Pregnancy_CanNotImpregnate"),
            trait("trait_GenderOptions_Pregnancy_CanBeImpregnated"),
        ],
    )

    options = sim.gender_options
    assert options.frame == "FEMININE"
    assert options.clothing == "WOMENSWEAR"
    assert options.toilet_use == "SITTING"
    assert options.lactation == "CANNOT"
    assert options.attracted_to == ["MALE", "FEMALE"]
    assert options.not_attracted_to == ["MALE"]
    assert options.woohoo_interests == ["FEMALE"]
    assert options.sexuality == "EXPLORING"
    assert options.can_impregnate is False
    assert options.can_be_impregnated is True


def test_localized_household_and_lot_links_follow_template_aliases() -> None:
    xml = """<root>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_Test" s="1" />
    <I c="PremadeHouseholdTemplate" n="premadeHouseholdTemplate_Test" s="2">
      <L n="_household_members"><U><T n="household_member_tag">a</T>
        <T n="sim_template">1</T></U></L>
    </I></root>"""
    entries = {item.instance_id: item for item in CombinedTuning.from_xml(xml)}
    world = WorldData(
        households={10: StarterHouseholdRecord(instance=10, name="premadeHouseholdTemplate_Test", members=[StarterMember(sim_id=20)])},
        lots={30: LotRecord(instance=30, household_id=10, household_name_key=100, household_description_key=101)},
    )
    catalog = Catalog(strings={100: "Localized Family", 101: "A household description."})
    bundle = build_premades(None, catalog, entries, {}, world=world, siminfo_index={})
    household = bundle.household(2)
    assert household is not None
    assert household.display_name == household.localized_name == "Localized Family"
    assert household.description == "A household description."
    assert household.lot_ids == [30] and household.lot_id == 30
    assert bundle.lot(30).household_id == 2
    assert bundle.household("Localized Family") is household
    assert bundle.household("Test") is household
    assert bundle.find_households("localized") == [household]
    assert household.to_dict()["lot_id"] == 30


def test_multiple_lots_do_not_choose_conflicting_localized_values() -> None:
    world = WorldData(
        households={10: StarterHouseholdRecord(instance=10, name="Family", members=[StarterMember(sim_id=20)])},
        lots={30: LotRecord(instance=30, household_id=10, household_name_key=100, household_description_key=101),
              31: LotRecord(instance=31, household_id=10, household_name_key=102, household_description_key=101)},
    )
    catalog = Catalog(strings={100: "First", 101: "Shared", 102: "Second"})
    bundle = build_premades(None, catalog, {}, {}, world=world, siminfo_index={})
    household = bundle.household(10)
    assert household.lot_ids == [30, 31] and household.lot_id is None
    assert household.localized_name is None and household.display_name == "Family"
    assert household.description == "Shared"
