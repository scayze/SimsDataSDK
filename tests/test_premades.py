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
