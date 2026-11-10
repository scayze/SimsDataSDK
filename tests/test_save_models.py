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
from sims4_sdk.save.models import SavedRelationship, SavedSim
from sims4_sdk.save.reader import (
    _link_special_relationships,
    sim_from_dict,
)


def build_catalog() -> Catalog:
    catalog = Catalog(
        traits={
            1: Trait(
                id=1,
                name="trait_Test",
                display_name="Test",
                description=None,
                trait_type="PERSONALITY",
            )
        },
        preferences={
            2: Preference(
                id=2,
                name="trait_Test_Likes_Cooking",
                display_name="Likes Cooking",
                description=None,
                preference_type="LIKE",
            )
        },
        aspiration_tracks={
            10: AspirationTrack(
                id=10,
                name="Track_Test",
                display_name="Test Track",
                description=None,
                aspiration_ids=[11],
            )
        },
        careers={
            20: Career(id=20, name="career_Test", start_track_id=21),
        },
        career_tracks={
            21: CareerTrack(
                id=21,
                name="Test_Track",
                display_name="Test Career",
                description=None,
                level_ids=[22, 23],
            )
        },
        career_levels={
            22: CareerLevel(
                id=22,
                name="career_Test_Level1",
                title="Intern",
                description=None,
                pay_per_hour=10,
            ),
            23: CareerLevel(
                id=23,
                name="career_Test_Level2",
                title="Manager",
                description=None,
                pay_per_hour=20,
            ),
        },
        milestones={
            30: Milestone(
                id=30,
                name="milestone_Test",
                display_name="Test Milestone",
                description=None,
            )
        },
        tuning_names={55: "skill_Test", 77: "statistic_Test"},
        tuning_classes={55: "Skill", 77: "Statistic"},
    )
    return catalog.finalize()


def test_sim_from_dict() -> None:
    data = {
        "sim_id": 100,
        "first_name": "Test",
        "last_name": "Sim",
        "age": 32,
        "gender": 8192,
        "extended_species": 1,
        "primary_aspiration": 10,
        "significant_other": 200,
        "attributes": {
            "trait_tracker": {"trait_ids": [1, 2, 999]},
            "sim_careers": {
                "careers": [
                    {
                        "career_uid": 20,
                        "track_uid": 21,
                        "track_level": 1,
                        "user_display_level": 2,
                        "pending_promotion": True,
                    }
                ],
                "career_history": [
                    {
                        "career_uid": 20,
                        "track_uid": 21,
                        "track_level": 0,
                        "user_display_level": 1,
                        "daily_pay": 100,
                    }
                ],
            },
            "skill_tracker": {"skills": [{"name_hash": 55, "value": 3.5}]},
            "statistics_tracker": {
                "statistics": [{"name_hash": 77, "value": 5.0}]
            },
            "genealogy_tracker": {
                "family_relations": [
                    {"relation_type": 0, "sim_id": 200},
                    {"relation_type": 1, "sim_id": 201},
                ]
            },
            "occult_tracker": {"occult_types": 4},
            "pregnancy_tracker": {"seed": 123, "parent_ids": [100, 200]},
            "death_tracker": {"death_type": 0, "death_time": 0},
            "event_data_tracker": {
                "objectives_completed": [1, 2],
                "milestones_completed": [3],
            },
        },
        "gameplay_data": {
            "developmental_milestone_tracker": {
                "active_milestones": [
                    {"milestone_id": 30, "state": 1, "age_completed": 32}
                ]
            }
        },
    }
    sim = sim_from_dict(data, build_catalog(), {200: "Parent One", 201: "Parent Two"})

    assert sim.full_name == "Test Sim"
    assert sim.age == "ADULT"
    assert sim.gender == "FEMALE"
    assert sim.species == "HUMAN"
    assert sim.occult == ["VAMPIRE"]
    assert sim.aspiration_track is not None and sim.aspiration_track.id == 10
    assert [trait.id for trait in sim.traits] == [1]
    assert [preference.id for preference in sim.preferences] == [2]
    assert sim.unknown_trait_ids == [999]
    assert sim.personality_traits == sim.traits
    assert [preference.name for preference in sim.likes] == ["trait_Test_Likes_Cooking"]
    assert sim.dislikes == []

    career = sim.career
    assert career is not None
    assert career.level_id == 23
    assert career.level.title == "Manager"
    assert career.pay_per_hour == 20
    assert career.pending_promotion is True
    assert career.history[0].daily_pay == 100

    assert sim.skills[0].name == "skill_Test"
    assert sim.skills[0].value == 3.5
    assert sim.statistics[0].name == "statistic_Test"

    assert sim.spouse_id == 200
    assert {relation.kind for relation in sim.parents} == {"MOTHER", "FATHER"}
    assert sim.parents[0].name == "Parent One"

    assert sim.milestones[0].milestone_id == 30
    assert sim.milestones[0].display_name == "Test Milestone"
    assert sim.objective_ids == [1, 2]
    assert sim.completed_milestone_ids == [3]
    assert sim.pregnancy["seed"] == 123
    assert sim.is_dead is False


def test_sim_gender_options_from_traits() -> None:
    def trait(trait_id: int, name: str) -> Trait:
        return Trait(
            id=trait_id,
            name=name,
            display_name=name,
            description=None,
            trait_type="GENDER_OPTIONS",
        )

    catalog = Catalog(
        traits={
            1: trait(1, "trait_GenderOptions_Frame_Masculine"),
            2: trait(2, "trait_GenderOptions_Clothing_MensWear"),
            3: trait(3, "trait_GenderOptions_AttractedTo_Female"),
            4: trait(4, "trait_GenderOptions_AttractedTo_NotFemale"),
            5: trait(5, "trait_SexualOrientation_WooHooInterests_Male"),
            6: trait(6, "trait_GenderOptions_Pregnancy_CanImpregnate"),
            7: trait(7, "trait_GenderOptions_Pregnancy_CanNot_BeImpregnated"),
        }
    ).finalize()

    sim = sim_from_dict(
        {
            "sim_id": 1,
            "first_name": "Test",
            "attributes": {"trait_tracker": {"trait_ids": [1, 2, 3, 4, 5, 6, 7]}},
        },
        catalog,
    )

    options = sim.gender_options
    assert options.frame == "MASCULINE"
    assert options.clothing == "MENSWEAR"
    assert options.attracted_to == ["FEMALE"]
    assert options.not_attracted_to == ["FEMALE"]
    assert options.woohoo_interests == ["MALE"]
    assert options.can_impregnate is True
    assert options.can_be_impregnated is False


def test_sim_relationship_tropes() -> None:
    catalog = Catalog(
        relationship_bits={
            362476: RelationshipBit(
                id=362476,
                name="romanceTrope_steamy",
                display_name="Steamy",
                description=None,
            ),
            306293: RelationshipBit(
                id=306293,
                name="familyTrope_close",
                display_name="Close",
                description=None,
            ),
        },
        family_trope_ids=[306293],
        romance_trope_ids=[362476],
    ).finalize()

    sim = sim_from_dict(
        {
            "sim_id": 1,
            "first_name": "Test",
            "attributes": {
                "genealogy_tracker": {
                    "relationship_tropes": [
                        {"sim_id": 2, "trope_id": 362476},
                        {"sim_id": 3, "trope_id": 306293},
                    ]
                }
            },
        },
        catalog,
        {2: "Partner Sim", 3: "Relative Sim"},
    )

    assert [trope.kind for trope in sim.tropes] == ["ROMANCE", "FAMILY"]
    assert [trope.trope_name for trope in sim.tropes] == ["Steamy", "Close"]
    assert [trope.sim_name for trope in sim.tropes] == ["Partner Sim", "Relative Sim"]


def test_link_special_relationships_from_bits() -> None:
    catalog = Catalog(
        steady_bit_id=15825,
        engagement_bit_id=15816,
        marriage_bit_id=15822,
    ).finalize()

    sims = {
        1: SavedSim(
            sim_id=1,
            first_name="One",
            relationships=[SavedRelationship(target_id=2, bits=[15825])],
        ),
        2: SavedSim(sim_id=2, first_name="Two"),
        3: SavedSim(sim_id=3, first_name="Three"),
        4: SavedSim(
            sim_id=4,
            first_name="Four",
            relationships=[SavedRelationship(target_id=5, bits=[15816])],
        ),
        5: SavedSim(sim_id=5, first_name="Five"),
        6: SavedSim(
            sim_id=6,
            first_name="Six",
            relationships=[SavedRelationship(target_id=7, bits=[15822])],
        ),
        7: SavedSim(sim_id=7, first_name="Seven"),
    }
    sims[3].fiance_id = 1
    sims[1].fiance_id = 3

    _link_special_relationships(sims, catalog)

    assert sims[1].steady_ids == [2]
    assert sims[1].steady_names == ["Two"]
    assert sims[1].fiance_name == "Three"
    assert sims[4].fiance_id == 5
    assert sims[4].fiance_name == "Five"
    assert sims[6].spouse_id == 7
    assert sims[6].spouse_name == "Seven"
