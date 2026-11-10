"""Unit tests for module-level relationship tuning extraction."""

from __future__ import annotations

from sims4_sdk.catalog import extract_relationship_tuning
from sims4_sdk.catalog.relationships import GLOBAL_MODULE
from sims4_sdk.core import CombinedTuning

XML = """<?xml version="1.0"?>
<root>
  <M n="relationships.relationship_tracker_tuning">
    <C n="DefaultRelationshipInHousehold">
      <L n="RelationshipSetupMap">
        <U>
          <E n="Family Link">FamilyMember</E>
          <L n="Default Relationship Setup">
            <U><U n="item">
              <L n="relationship_tracks">
                <U><T n="track">16650</T><T n="value">45</T></U>
              </L>
              <L n="relationship_bits"><T>15803</T></L>
            </U></U>
          </L>
        </U>
        <U>
          <E n="Family Link">Spouse</E>
          <L n="Default Relationship Setup">
            <U><U n="item">
              <L n="relationship_tracks">
                <U><T n="track">16651</T><T n="value">75</T></U>
              </L>
              <L n="relationship_bits"><T>10150</T></L>
              <L n="_loots"><T>5001</T></L>
            </U></U>
          </L>
        </U>
        <U>
          <E n="Family Link">Roommate</E>
          <L n="Default Relationship Setup">
            <U><U n="item">
              <L n="relationship_tracks">
                <U><T n="track">16650</T><T n="value">15</T></U>
              </L>
            </U></U>
          </L>
        </U>
      </L>
    </C>
  </M>
  <M n="relationships.global_relationship_tuning">
    <C n="RelationshipGlobalTuning">
      <T n="STEADY_RELATIONSHIP_BIT">15825</T>
      <T n="ENGAGEMENT_RELATIONSHIP_BIT">15816</T>
      <T n="MARRIAGE_RELATIONSHIP_BIT">15822</T>
    </C>
    <C n="TropeGlobalTuning">
      <L n="TROPES"><T>306293</T><T>310888</T></L>
      <L n="ROMANCE_TROPES"><T>362476</T><T>362475</T></L>
    </C>
  </M>
  <M n="world.premade_sim_relationships">
    <C n="PremadeSimRelationships">
      <L n="RELATIONSHIP_MAP">
        <U><T n="relationship_loot">9001</T><T n="sim_a">100</T><T n="sim_b">200</T></U>
      </L>
    </C>
  </M>
  <I c="LootActions" i="action" m="interactions.utils.loot" n="loot_test" s="9001">
    <L n="loot_actions">
      <V t="actions"><T n="actions">9002</T></V>
      <V t="statistics"><V n="statistics" t="relationship_set"><U>
        <T n="track">16650</T><T n="value">60</T>
      </U></V></V>
    </L>
  </I>
  <I c="LootActions" i="action" m="interactions.utils.loot" n="loot_nested" s="9002">
    <L n="loot_actions">
      <V t="statistics"><V n="statistics" t="relationship_set"><U>
        <T n="track">16651</T><T n="value">20</T>
      </U></V></V>
    </L>
  </I>
  <I c="RelationshipTrack" i="statistic" m="relationships.relationship_track" n="LTR_Friendship_Main" s="16650">
    <V n="bit_data_tuning" t="bit_set"><U n="bit_set"><L n="bit_data">
      <U><T n="bit">15797</T><T n="minimum_value">35</T><T n="maximum_value">60</T></U>
    </L></U></V>
  </I>
  <I c="RelationshipTrack" i="statistic" m="relationships.relationship_track" n="LTR_Romance_Main" s="16651">
    <V n="bit_data_tuning" t="bit_set"><U n="bit_set"><L n="bit_data">
      <U><T n="bit">15829</T><T n="minimum_value">25</T><T n="maximum_value">75</T></U>
    </L></U></V>
  </I>
</root>
"""


def _extract():
    tuning = CombinedTuning.from_xml(XML)
    entries = {entry.instance_id: entry for entry in tuning}
    modules = {
        name: tuning for name in (
            "relationships.relationship_tracker_tuning",
            "world.premade_sim_relationships",
            GLOBAL_MODULE,
        )
    }
    return extract_relationship_tuning(modules, entries)


def test_default_relationship_values() -> None:
    data = _extract()
    family = data.defaults["FamilyMember"]
    spouse = data.defaults["Spouse"]
    roommate = data.defaults["Roommate"]

    assert family.track(16650).value == 45
    assert family.bit_ids == [15803]
    assert spouse.track(16651).value == 75
    assert spouse.bit_ids == [10150]
    assert spouse.loot_ids == [5001]
    assert roommate.track(16650).value == 15


def test_cross_household_relationship_loot() -> None:
    data = _extract()
    assert len(data.pairs) == 1
    relationship = data.pairs[0]
    assert relationship.sim_a == 100
    assert relationship.sim_b == 200
    assert relationship.friendship == 60
    assert relationship.romance == 20
    assert relationship.track(16650).track_name == "LTR_Friendship_Main"


def test_relationship_track_ranges() -> None:
    data = _extract()
    friend = data.track_ranges[15797]
    assert friend.track_id == 16650
    assert friend.min_value == 35
    assert friend.max_value == 60

    lovebirds = data.track_ranges[15829]
    assert lovebirds.track_id == 16651
    assert lovebirds.min_value == 25
    assert lovebirds.max_value == 75


def test_global_relationship_bits_and_tropes() -> None:
    data = _extract()
    assert data.steady_bit_id == 15825
    assert data.engagement_bit_id == 15816
    assert data.marriage_bit_id == 15822
    assert data.family_trope_ids == [306293, 310888]
    assert data.romance_trope_ids == [362476, 362475]
