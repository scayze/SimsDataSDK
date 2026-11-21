from sims4_sdk.catalog import (
    Catalog,
    LootBitOperation,
    LotRecord,
    Preference,
    PremadeFamilyFixup,
    PremadeRelationship,
    StarterHouseholdRecord,
    StarterMember,
    StarterRelation,
    PremadeSim,
    SkillLevel,
    Trait,
    WorldData,
    build_premades,
)
from sims4_sdk.core import CombinedTuning
import struct
from types import SimpleNamespace

from sims4_sdk.core import DBPF


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


def test_species_from_siminfo_takes_precedence_and_exports(monkeypatch) -> None:
    xml = '''<root><I c="PremadeSimTemplate" n="Horse" s="1">
      <U n="_sim_creation_info"><T n="resource_key">025ed6f4:00000000:0000000000001234</T></U>
      <U n="_traits"><L n="explicit"><T>2</T></L></U>
    </I></root>'''
    entries = {item.instance_id: item for item in CombinedTuning.from_xml(xml)}
    trait = Trait(id=2, name="trait_Species_Dog", display_name="Dog", description=None, trait_type="HIDDEN")
    raw = bytearray(52)
    struct.pack_into("<I", raw, 0, 38)
    struct.pack_into("<I", raw, 48, 6)
    monkeypatch.setattr(DBPF, "read_entry", lambda *_: bytes(raw))
    bundle = build_premades(None, Catalog(traits={2: trait}), entries, {},
                            siminfo_index={0x1234: (SimpleNamespace(path="unused"), None)})
    sim = bundle.sim(1)
    assert (sim.species_raw, sim.species) == (6, "Horse")
    assert sim.to_dict()["species_raw"] == 6
    assert '"species": "Horse"' in sim.to_json()
    sim.species_raw = 4
    assert sim.species == "SmallDog"
    sim.species_raw = 999
    assert sim.species == "Dog"
    sim.traits.clear()
    assert sim.species is None


def test_starter_species_fills_only_missing_siminfo_species() -> None:
    from sims4_sdk.catalog.premades import _apply_hints

    sim = PremadeSim(id=1, name="Test", first_name="", last_name="")
    _apply_hints(Catalog(), sim, StarterMember(species_raw=6))
    assert (sim.species_raw, sim.species) == (6, "Horse")
    _apply_hints(Catalog(), sim, StarterMember(species_raw=1))
    assert (sim.species_raw, sim.species) == (6, "Horse")


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


def test_townie_street_variant_and_serialization() -> None:
    xml = '''<root><g>
      <V x="1" t="enabled"><r n="enabled" x="2" /></V>
      <T x="2">20384</T><V x="3" t="disabled" />
    </g>
    <I c="PremadeHouseholdTemplate" n="Enabled" s="1"><r n="_townie_street" x="1" /></I>
    <I c="PremadeHouseholdTemplate" n="Disabled" s="2"><r n="_townie_street" x="3" /></I>
    <I c="PremadeHouseholdTemplate" n="Missing" s="3" />
    <I c="PremadeHouseholdTemplate" n="Incomplete" s="4"><V n="_townie_street" t="enabled"><r x="99" /></V></I>
    <I c="PremadeHouseholdTemplate" n="Unresolved" s="5"><r n="_townie_street" x="99" /></I>
    </root>'''
    entries = {item.instance_id: item for item in CombinedTuning.from_xml(xml)}
    bundle = build_premades(None, Catalog(), entries, {}, siminfo_index={})
    assert (bundle.household(1).townie_street_status, bundle.household(1).townie_street_id) == ("enabled", 20384)
    assert (bundle.household(2).townie_street_status, bundle.household(2).townie_street_id) == ("disabled", None)
    assert (bundle.household(3).townie_street_status, bundle.household(3).townie_street_id) == ("unknown", None)
    assert (bundle.household(4).townie_street_status, bundle.household(4).townie_street_id) == ("enabled", None)
    assert bundle.household(5).townie_street_status == "unknown"
    data = bundle.household(1).to_dict()
    assert data["townie_street_status"] == "enabled" and data["townie_street_id"] == 20384
    assert '"townie_street_id": 20384' in bundle.household(1).to_json()


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
    assert bundle.sim(1).normal_game_usage is True
    assert bundle.sim(1).scenario_usage is None


def test_placed_household_wins_over_unplaced_duplicate() -> None:
    from sims4_sdk.catalog.premades import HouseholdMember, PremadeHousehold, _merge_world

    sim = PremadeSim(id=1, name="Penny", first_name="Penny", last_name="Pizzazz")
    household = PremadeHousehold(id=2, name="hH_Template_Pizzazz", members=[
        HouseholdMember(tag="a", sim_template_id=1, sim_name="Penny", full_name="Penny Pizzazz")
    ])
    world = WorldData(
        households={
            10: StarterHouseholdRecord(instance=10, name="hH_Template_Pinku", funds=20000,
                members=[StarterMember(first_name="Penny", last_name="Pizzazz", aspiration_track_id=25441, career_id=123)]),
            11: StarterHouseholdRecord(instance=11, name="hH_Template_Pizzazz", funds=4000,
                members=[StarterMember(first_name="Penny", last_name="Pizzazz", aspiration_track_id=144947)]),
            12: StarterHouseholdRecord(instance=12, name="Other", members=[StarterMember(first_name="Other")]),
        },
        lots={30: LotRecord(instance=30, household_id=11)},
    )
    households = {2: household}
    aliases, ids = _merge_world(Catalog(), {1: sim}, households, world)

    assert sim.aspiration_track_id == 144947
    assert sim.career_id is None
    assert household.funds == 4000
    assert ids == {11: 2}
    assert "hH_Template_Pinku" not in aliases
    assert household.starter_record_ids == [10, 11]
    assert household.selected_starter_record_id == 11
    assert household.starter_selection_reason == "lot"
    assert household.to_dict()["starter_record_ids"] == [10, 11]
    assert '"selected_starter_record_id": 11' in household.to_json()
    assert 12 in households
    assert world.households[10].members[0].aspiration_track_id == 25441


def test_unplaced_duplicate_selection_and_ambiguity() -> None:
    from sims4_sdk.catalog.premades import HouseholdMember, PremadeHousehold, _merge_world

    def merge(funds, placed=()):
        sim = PremadeSim(id=1, name="Test", first_name="Alex", last_name="Test")
        household = PremadeHousehold(id=2, name="Template", funds=funds, members=[
            HouseholdMember(tag="a", sim_template_id=1, sim_name="Test", full_name="Alex Test")
        ])
        world = WorldData(households={
            10: StarterHouseholdRecord(instance=10, name="First", funds=100,
                members=[StarterMember(first_name="Alex", last_name="Test", aspiration_track_id=1)]),
            11: StarterHouseholdRecord(instance=11, name="Second", funds=200,
                members=[StarterMember(first_name="Alex", last_name="Test", aspiration_track_id=2)]),
        }, lots={i: LotRecord(instance=i, household_id=i) for i in placed})
        _, ids = _merge_world(Catalog(), {1: sim}, {2: household}, world)
        return sim, household, ids

    sim, household, ids = merge(200)
    assert (sim.aspiration_track_id, household.selected_starter_record_id, household.starter_selection_reason) == (2, 11, "funds")
    assert ids == {11: 2}
    sim, household, ids = merge(None)
    assert (sim.aspiration_track_id, household.selected_starter_record_id, household.starter_selection_reason) == (None, None, "ambiguous")
    assert household.starter_record_ids == [10, 11] and ids == {}
    sim, household, ids = merge(200, placed=(10, 11))
    assert sim.aspiration_track_id is None and household.starter_selection_reason == "ambiguous"
    assert ids == {}


def test_same_named_tuning_households_do_not_get_an_arbitrary_match() -> None:
    from sims4_sdk.catalog.premades import HouseholdMember, PremadeHousehold, _merge_world

    sims = {i: PremadeSim(id=i, name=f"Sim{i}", first_name="Alex", last_name="Test") for i in (1, 2)}
    households = {i + 10: PremadeHousehold(id=i + 10, name=f"Household{i}", members=[
        HouseholdMember(tag="a", sim_template_id=i, sim_name=f"Sim{i}", full_name="Alex Test")
    ]) for i in (1, 2)}
    world = WorldData(households={20: StarterHouseholdRecord(instance=20, name="Other", members=[
        StarterMember(first_name="Alex", last_name="Test", aspiration_track_id=100)
    ])}, lots={30: LotRecord(instance=30, household_id=20)})
    _, ids = _merge_world(Catalog(), sims, households, world)
    assert ids == {}
    assert all(sim.aspiration_track_id is None for sim in sims.values())
    assert all(household.starter_record_ids == [20] and household.starter_selection_reason == "ambiguous"
               for household in households.values())


def test_scenario_name_and_world_placement_are_independent_evidence() -> None:
    xml = '''<root>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_Scenario_Test" s="1" />
    <I c="PremadeSimTemplate" n="premadeSimTemplate_Other" s="2" />
    <I c="PremadeSimTemplate" n="premadeSimTemplate_Unknown" s="5" />
    <I c="PremadeHouseholdTemplate" n="premadeHouseholdTemplate_Scenario_Test" s="3">
      <L n="_household_members"><U><T n="household_member_tag">a</T>
      <T n="sim_template">1</T></U></L></I>
    <I c="PremadeHouseholdTemplate" n="OrdinaryName" s="4">
      <L n="_household_members"><U><T n="household_member_tag">a</T>
      <T n="sim_template">2</T></U></L></I>
    <I c="Scenario" n="test" s="9">
      <L n="compatible_premade_household_templates">
        <T>b3c438f0:00000000:000000000000000b</T>
      </L></I></root>'''
    entries = {item.instance_id: item for item in CombinedTuning.from_xml(xml)}
    world = WorldData(
        households={10: StarterHouseholdRecord(instance=10, name="premadeHouseholdTemplate_Scenario_Test", members=[StarterMember(sim_id=20)]),
                    11: StarterHouseholdRecord(instance=11, name="OrdinaryName", members=[StarterMember(sim_id=21)])},
        lots={30: LotRecord(instance=30, household_id=10)},
    )
    bundle = build_premades(None, Catalog(), entries, {}, world=world, siminfo_index={})
    sim = bundle.sim(1)
    assert sim.scenario_usage is True and sim.normal_game_usage is True
    assert {item.id for item in bundle.find_sims(origin="scenario")} == {1, 2}
    assert bundle.find_sims(origin="normal") == [sim]
    assert bundle.find_sims(origin="both") == [sim]
    assert [item.id for item in bundle.find_sims(origin="unknown")] == [5]
    assert sim.to_dict()["scenario_usage"] is True
    assert sim.to_dict()["normal_game_usage"] is True


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


def test_family_tree_links_ancestors_fixups_parentless_siblings_and_loot_parents() -> None:
    xml = """<root>
    <I c="TunablePremadeAncestor" n="PremadeAncestor_Grandma" s="10">
      <V n="full_name" t="enabled"><T n="enabled">0x10</T></V>
      <E n="gender">FEMALE</E>
      <V n="death_trait" t="enabled"><T n="enabled">999</T></V>
      <V n="thumbnail" t="enabled"><T n="enabled">2f7d0004:00000000:1111111111111111</T></V>
    </I>
    <I c="TunablePremadeAncestor" n="PremadeAncestor_Grandpa" s="11">
      <V n="full_name" t="enabled"><T n="enabled">0x11</T></V>
    </I>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_Parent" s="20">
      <U n="_sim_creation_info">
        <T n="first_name">0x20</T>
        <V n="last_name" t="specify_last_name"><T n="specify_last_name">0x21</T></V>
      </U>
    </I>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_SecretParent" s="25">
      <U n="_sim_creation_info">
        <T n="first_name">0x25</T>
        <V n="last_name" t="specify_last_name"><T n="specify_last_name">0x26</T></V>
      </U>
    </I>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_ChildA" s="30">
      <U n="_sim_creation_info">
        <T n="first_name">0x30</T>
        <V n="last_name" t="specify_last_name"><T n="specify_last_name">0x21</T></V>
      </U>
    </I>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_ChildB" s="31">
      <U n="_sim_creation_info">
        <T n="first_name">0x31</T>
        <V n="last_name" t="specify_last_name"><T n="specify_last_name">0x21</T></V>
      </U>
    </I>
    <I c="PremadeSimTemplate" n="premadeSimTemplate_OutcastChild" s="32">
      <U n="_sim_creation_info">
        <T n="first_name">0x32</T>
        <V n="last_name" t="specify_last_name"><T n="specify_last_name">0x33</T></V>
      </U>
    </I>
    <I c="PremadeHouseholdTemplate" n="HH_Main" s="100">
      <L n="_household_members">
        <U><T n="household_member_tag">m1</T><T n="sim_template">30</T></U>
        <U><T n="household_member_tag">m2</T><T n="sim_template">31</T></U>
      </L>
      <L n="_household_relationship">
        <U><T n="is_parentless_sibling">True</T><T n="x">m1</T><T n="y">m2</T></U>
      </L>
    </I>
    </root>"""
    entries = {item.instance_id: item for item in CombinedTuning.from_xml(xml)}
    world = WorldData(
        households={
            200: StarterHouseholdRecord(
                instance=200,
                name="Purdue",
                members=[
                    StarterMember(
                        first_name="Cassidy",
                        last_name="Purdue",
                        sim_id=501,
                        relations=[StarterRelation(relation_type=0, target_id=999999)],
                    ),
                    StarterMember(
                        first_name="Ollie",
                        last_name="Purdue",
                        sim_id=502,
                        relations=[StarterRelation(relation_type=0, target_id=999999)],
                    ),
                ],
            )
        }
    )
    catalog = Catalog(
        strings={
            0x10: "Cornelia Goth",
            0x11: "Gunther Goth",
            0x20: "Mortimer",
            0x21: "Goth",
            0x25: "Adekoya",
            0x26: "Darong",
            0x30: "Cassandra",
            0x31: "Alexander",
            0x32: "Johnny",
            0x33: "Zest",
        },
        family_fixups=[
            PremadeFamilyFixup(sim_a=10, sim_b=11, flags=["SPOUSE"]),
            PremadeFamilyFixup(sim_a=10, sim_b=20, flags=["PARENT"]),
            PremadeFamilyFixup(sim_a=11, sim_b=20, flags=["PARENT"]),
            PremadeFamilyFixup(sim_a=20, sim_b=30, flags=["PARENT"]),
            PremadeFamilyFixup(sim_a=25, sim_b=30, flags=["SECRET_PARENT"]),
        ],
        premade_relationships=[
            PremadeRelationship(
                sim_a=32,
                sim_b=20,
                bit_ids=[8809],
                bit_operations=[
                    LootBitOperation(
                        bit_id=8809,
                        recipients="Actor",
                        targets="TargetSim",
                        is_parent_relationship=True,
                    )
                ],
            )
        ],
    )
    bundle = build_premades(None, catalog, entries, {}, world=world, siminfo_index={})

    grandma = bundle.ancestor("Cornelia Goth")
    assert grandma is not None
    assert grandma.death_trait_id == 999
    assert grandma.thumbnail == "2f7d0004:00000000:1111111111111111"
    assert grandma.spouse_name == "Gunther Goth"
    assert grandma.children == ["Mortimer Goth"]

    mortimer = bundle.sim("Mortimer Goth")
    assert set(mortimer.parents) == {"Cornelia Goth", "Gunther Goth"}
    assert set(mortimer.children) == {"Cassandra Goth", "Johnny Zest"}

    cassandra = bundle.sim("Cassandra Goth")
    alexander = bundle.sim("Alexander Goth")
    johnny = bundle.sim("Johnny Zest")
    assert "Alexander Goth" in cassandra.siblings
    assert "Cassandra Goth" in alexander.siblings
    assert "Johnny Zest" in cassandra.siblings
    assert "Cassandra Goth" in johnny.siblings
    assert johnny.parents == ["Mortimer Goth"]

    cassidy = bundle.sim("Cassidy Purdue")
    ollie = bundle.sim("Ollie Purdue")
    assert cassidy.siblings == ["Ollie Purdue"]
    assert ollie.siblings == ["Cassidy Purdue"]

    tree = bundle.family_tree("Cassandra Goth")
    assert tree is not None
    assert tree.root.full_name == "Cassandra Goth"
    assert tree.root.secret_parent_ids == [25]
    ancestor_names = {node.full_name for node in tree.ancestors_of()}
    assert ancestor_names == {"Mortimer Goth", "Adekoya Darong", "Cornelia Goth", "Gunther Goth"}
    descendant_names = {node.full_name for node in tree.descendants_of(10)}
    assert descendant_names == {"Mortimer Goth", "Cassandra Goth", "Johnny Zest"}
    assert tree.to_dict()["nodes"][str(cassandra.id)]["full_name"] == "Cassandra Goth"
