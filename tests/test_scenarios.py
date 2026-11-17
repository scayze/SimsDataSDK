import json

from sims4_sdk import Sims4Workspace
from sims4_sdk.catalog import Catalog, StaticData, TuningSource, build_premades, extract_scenarios
from sims4_sdk.core import CombinedTuning, ResourceKey


def fixture_entries(extra=""):
    xml = f'''<root><g><T x="1">20</T></g>
    <I c="Scenario" n="scenario_Test" s="10">
      <T n="scenario_name">0x10</T><T n="scenario_description">0x11</T>
      <L n="scenario_role_data"><U><T n="role">40</T></U></L>
      <L n="scenario_npc_sims"><U><r n="sim_filter" x="1" /></U>
        <U><T n="sim_filter">999</T></U></L>
      <L n="compatible_premade_household_templates"><T>b3c438f0:00000000:000000000000002a</T></L>
      <T n="starting_phase">41</T>
    </I>
    <I c="ScenarioRole" n="role_Test" s="40"><L n="criteria"><U><T n="age">ADULT</T></U></L></I>
    <I c="TunableSimFilter" n="filter_Test" s="20"><T n="_template_chooser">30</T>
      <V n="_household_templates_override" t="enabled"><L n="enabled"><T>80</T><T>888</T></L></V></I>
    <I c="TunableTemplateChooser" n="chooser_Test" s="30"><L n="_templates">
      <U><T n="template">50</T></U><U><T n="template">777</T></U></L></I>
    <I c="TunableSimTemplate" n="template_Test" s="50"><U n="_sim_creation_info">
      <U n="full_name"><T n="first_name">0x12</T><V n="last_name" t="specify_last_name"><T n="specify_last_name">0x13</T></V></U>
      <V n="resource_key" t="enabled"><T n="enabled">025ed6f4:00000000:0000000000000123</T></V>
    </U></I>
    <I c="HouseholdTemplate" n="hh_Test" s="80"><L n="_household_members"><U><T n="sim_template">50</T></U></L></I>
    <I c="PremadeSimTemplate" n="premade_Test" s="60"><U n="_sim_creation_info">
      <T n="first_name">0x12</T><V n="last_name" t="specify_last_name"><T n="specify_last_name">0x13</T></V>
      <T n="resource_key">025ed6f4:00000000:0000000000000123</T>
    </U></I>
    <I c="SituationJob" n="job_Test" s="70"><T n="filter">20</T></I>
    <I c="SpecificSimCustomStatesSituation" n="situation_Test" s="71"><T n="specific_sim_job">70</T></I>
    <I c="SchedulingWalkbyDirector" n="walkbyDirector_Residential_Test" s="72"><L n="situation_shifts">
      <U><L n="weighted_situations"><U><T n="situation">71</T></U></L></U></L></I>
    {extra}</root>'''
    return {entry.instance_id: entry for entry in CombinedTuning.from_xml(xml)}


def test_extract_and_link_scenario_and_world_npc_data(tmp_path):
    entries = fixture_entries()
    source = TuningSource("test.package", "BASE")
    strings = {0x10: "Test Scenario", 0x11: "A scenario", 0x12: "Casey", 0x13: "Test"}
    data = extract_scenarios(entries, {10: source}, strings)
    scenario = data.scenario("TEST SCENARIO")
    assert scenario.id == 10 and scenario.source == source
    assert scenario.description == "A scenario"
    assert scenario.npc_filter_ids == [20, 999]  # retain unresolved targets
    assert scenario.role_ids == [40] and scenario.starting_phase_id == 41
    assert scenario.household_keys == [ResourceKey(0xB3C438F0, 0, 42)]
    assert data.roles[40].criteria[0]["children"][0]["value"] == "ADULT"
    assert data.sim_filters[20].household_template_ids == [80, 888]
    assert data.template_choosers[30].template_ids == [50, 777]
    assert data.household_templates[80].sim_template_ids == [50]
    assert data.sim_templates[50].first_name == "Casey"
    assert data.walkby_directors[72].situation_ids == [71]
    bundle = build_premades(None, Catalog(strings=strings), entries, {}, siminfo_index={}, scenario_data=data)
    sim = bundle.sim(60)
    assert sim.scenario_ids == [10] and sim.scenario_usage is True
    assert sim.normal_walkby_director_ids == [72] and sim.normal_game_usage is True
    static = StaticData(premades=bundle, scenario_data=data)
    ws = Sims4Workspace(install_dir=tmp_path, static=static)
    assert ws.scenario("test scenario").id == 10
    assert ws.find_scenario(10).id == 10
    assert ws.find_scenarios("TEST")[0].id == 10
    assert ws.find_sims(origin="both") == [sim]
    payload = json.loads(static.to_json())
    assert payload["scenario_data"]["scenarios"]["10"]["npc_filter_ids"] == [20, 999]
    assert payload["scenario_data"]["sim_templates"]["50"]["siminfo_key"] == "025ED6F4!00000000!0000000000000123"
    path = static.save(tmp_path / "snapshot.pkl")
    assert StaticData.load(path).scenario(10).name == "scenario_Test"


def test_matching_siminfo_requires_unique_name_and_key():
    extra = '''<I c="PremadeSimTemplate" n="duplicate" s="61"><U n="_sim_creation_info">
      <T n="first_name">0x12</T><T n="last_name">0x13</T>
      <T n="resource_key">025ed6f4:00000000:0000000000000123</T>
    </U></I>'''
    entries = fixture_entries(extra)
    strings = {0x12: "Casey", 0x13: "Test"}
    data = extract_scenarios(entries, {}, strings)
    bundle = build_premades(None, Catalog(strings=strings), entries, {}, siminfo_index={}, scenario_data=data)
    assert all(sim.scenario_usage is None and sim.normal_game_usage is None for sim in bundle.sims)


def test_nonresidential_walkby_is_not_normal_world_evidence():
    entries = fixture_entries()
    entries[72].raw.set("n", "walkbyDirector_Scenario_Test")
    strings = {0x12: "Casey", 0x13: "Test"}
    data = extract_scenarios(entries, {}, strings)
    bundle = build_premades(None, Catalog(strings=strings), entries, {}, siminfo_index={}, scenario_data=data)
    assert bundle.sim(60).scenario_usage is True
    assert bundle.sim(60).normal_game_usage is None


def test_missing_scenario_data_in_old_snapshot_is_unknown(tmp_path):
    static = StaticData()
    del static.__dict__["scenario_data"]
    path = static.save(tmp_path / "old.pkl")
    loaded = StaticData.load(path)
    assert loaded.scenario(10) is None
    assert loaded.find_scenarios() == []
    assert loaded.to_dict()["scenario_data"] is None


def test_bad_tuning_is_reported_without_losing_other_models():
    class BrokenEntry:
        cls = "Scenario"
        name = "broken"

        @property
        def raw(self):
            raise ValueError("bad tuning")

    entries = fixture_entries()
    entries[1000] = BrokenEntry()
    data = extract_scenarios(entries, {}, {})
    assert 10 in data.scenarios
    assert len(data.diagnostics) == 1
    assert data.diagnostics[0].tuning_id == 1000
    assert data.diagnostics[0].recoverable is True
