from pathlib import Path
from types import SimpleNamespace

from sims4_sdk.catalog import (
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Trait,
)
from sims4_sdk.save.models import (
    SavedFamilyRelation,
    SavedSkill,
)
from sims4_sdk.validation import (
    WikiCatalogEntry,
    compare_catalog,
    compare_sim,
    parse_catalog_aspirations,
    parse_catalog_likes,
    parse_catalog_milestones,
    parse_catalog_traits,
    parse_sim,
)
from sims4_sdk.validation.models import DomainCoverage, ValidationReport
from sims4_sdk.validation.normalize import names_match

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_bella() -> None:
    sim = parse_sim(read("bella.wiki"), "Bella Goth")
    assert sim is not None
    assert sim.name == "Bella Goth"
    assert sim.sex == "Female"
    assert sim.age == "Young Adult"
    assert sim.career == "Secret Agent"
    assert sim.career_level == "Intelligence Researcher"
    assert sim.aspiration == "Party Animal"
    assert sim.traits == ["Good", "Family-Oriented", "Romantic", "Gregarious"]
    assert sim.spouse == ["Mortimer Goth"]
    assert sim.children == ["Cassandra Goth", "Alexander Goth"]
    assert sim.skills == {"charisma": 2, "fitness": 2, "programming": 2}
    assert [rel.name for rel in sim.relationships] == [
        "Mortimer Goth",
        "Cassandra Goth",
        "Alexander Goth",
    ]
    assert sim.relationships[0].friendship == 45
    assert sim.relationships[0].romance == 75


def test_parse_trait_table() -> None:
    entries = parse_catalog_traits(read("traits.wiki"))
    assert [entry.name for entry in entries] == [
        "Ambitious",
        "Cheerful",
        "Family-Oriented",
    ]
    assert entries[0].pack == "TS4"


def test_parse_aspiration_table() -> None:
    entries = parse_catalog_aspirations(read("aspirations.wiki"))
    assert [entry.name for entry in entries] == [
        "Friend of the Animals",
        "Bodybuilder",
    ]


def test_parse_milestone_table() -> None:
    entries = parse_catalog_milestones(read("milestones.wiki"))
    assert [entry.name for entry in entries] == ["Learned to Reach", "Learned to Grab"]


def test_parse_likes_table() -> None:
    entries = parse_catalog_likes(read("likes.wiki"))
    assert [entry.name for entry in entries] == ["Acting", "Baking", "Fitness"]


def test_names_match_aliases() -> None:
    assert names_match("Family-Oriented", "Family Oriented")
    assert names_match("Red", "Likes the Color Red", min_length=3)
    assert names_match("Master Actor/Master Actress", "Master Actor")
    assert names_match("Well-Balanced Practicioner", "Well-Balanced Practitioner")
    assert not names_match("Good", "Evil")


def test_compare_sim_matches() -> None:
    wiki = parse_sim(read("bella.wiki"), "Bella Goth")
    assert wiki is not None

    traits = [
        Trait(id=1, name="trait_Good", display_name="Good", description=None, trait_type="PERSONALITY"),
        Trait(
            id=2,
            name="trait_FamilyOriented",
            display_name="Family-Oriented",
            description=None,
            trait_type="PERSONALITY",
        ),
        Trait(
            id=3,
            name="Trait_Romantic",
            display_name="Romantic",
            description=None,
            trait_type="PERSONALITY",
        ),
        Trait(
            id=4,
            name="trait_Gregarious",
            display_name="Gregarious",
            description=None,
            trait_type="ASPIRATION",
        ),
    ]
    career = SimpleNamespace(
        title="Intelligence Researcher",
        track_name="Secret Agent",
        career_name="career_Adult_SecretAgent",
    )
    sdk = SimpleNamespace(
        full_name="Bella Goth",
        age="YOUNGADULT",
        gender="FEMALE",
        visible_traits=traits,
        aspiration_track=AspirationTrack(
            id=1,
            name="Track_Popularity_C",
            display_name="Party Animal",
            description=None,
        ),
        aspiration=None,
        career=career,
        spouse_name="Mortimer Goth",
        children=[
            SavedFamilyRelation("CHILD", 1, "Cassandra Goth"),
            SavedFamilyRelation("CHILD", 2, "Alexander Goth"),
        ],
        parents=[],
        skills=[
            SavedSkill(1, "statistic_Skill_AdultMajor_Charisma", "Skill", 1540.0),
            SavedSkill(2, "skill_Fitness", "Skill", 1585.0),
            SavedSkill(3, "statistic_Skill_AdultMajor_Programming", "Skill", 1540.0),
        ],
        relationships=[],
    )

    comparison = compare_sim(sdk, wiki)
    assert comparison.score == 1.0
    statuses = {field.field: field.status for field in comparison.fields}
    assert statuses["traits"] == "match"
    assert statuses["skills"] == "match"
    assert statuses["relationships"] == "not_available"


def test_compare_catalog_coverage() -> None:
    coverage = compare_catalog(
        "traits",
        [WikiCatalogEntry("Ambitious"), WikiCatalogEntry("Cheerful")],
        ["Ambitious", "Cheerful", "Extra"],
    )
    assert coverage.wiki_count == 2
    assert coverage.sdk_count == 3
    assert coverage.matched == ["Ambitious", "Cheerful"]
    assert coverage.extra_in_sdk == ["Extra"]
    assert coverage.coverage == 1.0


def test_report_rendering() -> None:
    report = ValidationReport(
        catalog={
            "traits": DomainCoverage(
                domain="traits",
                wiki_count=2,
                sdk_count=2,
                matched=["Ambitious"],
                missing_in_sdk=["Cheerful"],
            )
        },
        sims=[],
    )
    markdown = report.to_markdown()
    assert "Sims Wiki validation report" in markdown
    assert "missing in SDK" in markdown
    assert report.to_dict()["summary"]["catalog"]["traits"]["wiki"] == 2
