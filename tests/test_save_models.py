from sims4_sdk.catalog import (
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    Milestone,
    Preference,
    Trait,
)
from sims4_sdk.save.reader import sim_from_dict


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
