from sims4_sdk.catalog import (
    Preference,
    PremadeSim,
    SkillLevel,
    Trait,
    parse_resource_key,
)


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
