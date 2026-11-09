"""Schemas for the subset of save-game protobuf messages the SDK exposes.

Field numbers and names come from EA's generated protobuf classes.  Unknown
fields are skipped by the decoder, so these schemas can stay focused on the data
we actually use.
"""

from __future__ import annotations

from typing import Mapping

from .protobuf import FieldSpec

__all__ = ["SCHEMAS"]


def f(
    name: str,
    kind: str = "uint",
    *,
    repeated: bool = False,
    message: str | None = None,
) -> FieldSpec:
    return FieldSpec(name=name, kind=kind, repeated=repeated, message=message)


SCHEMAS: dict[str, Mapping[int, FieldSpec]] = {
    # ------------------------------------------------------------------
    # top-level save structure
    # ------------------------------------------------------------------
    "SaveGameData": {
        1: f("guid"),
        2: f("save_slot", "message", message="SaveSlotData"),
        3: f("account", "message", message="AccountData"),
        4: f("neighborhoods", "message", repeated=True, message="NeighborhoodData"),
        5: f("households", "message", repeated=True, message="HouseholdData"),
        6: f("sims", "message", repeated=True, message="SimData"),
        7: f("zones", "message", repeated=True, message="ZoneData"),
        14: f("gameplay_data", "message", message="GameplayData"),
        16: f("relgraph", "message", message="SimRelationshipGraphData"),
    },
    "SimRelationshipGraphData": {
        1: f("nodes", "message", repeated=True, message="SimRelationshipNode"),
    },
    "SimRelationshipNode": {
        1: f("node_id"),
        2: f("sim_id"),
        4: f("first_name", "string"),
        5: f("last_name", "string"),
        6: f("outgoing_edges", "message", repeated=True, message="SimRelationshipEdge"),
    },
    "SimRelationshipEdge": {
        1: f("target_node_id"),
        2: f("edge_data"),
    },
    "SaveSlotData": {
        1: f("slot_id"),
        3: f("last_neighborhood"),
        5: f("last_zone"),
        7: f("is_migrated", "bool"),
        9: f("slot_name", "string"),
        10: f("timestamp"),
        11: f("active_household_id"),
        12: f("nucleus_id"),
        13: f("s4_guid_seed"),
        14: f("compatibility_version"),
        16: f("tutorial_mode", "int"),
    },
    "AccountData": {
        3: f("email", "string"),
        4: f("created"),
        5: f("last_login"),
        10: f("client_version", "string"),
        12: f("save_slot_id"),
        18: f("number_of_saves"),
        19: f("number_of_saves_mods"),
        20: f("number_of_saves_script_mods"),
    },
    "NeighborhoodData": {
        1: f("neighborhood_id"),
        3: f("name", "string"),
        4: f("region_id"),
        10: f("description", "string"),
    },
    "HouseholdData": {
        1: f("account_id"),
        2: f("household_id"),
        3: f("name", "string"),
        4: f("home_zone"),
        5: f("money"),
        9: f("last_played_sim_id"),
        10: f("creation_time"),
        11: f("sims", "message", message="IdList"),
        12: f("owned_lots", "message", message="IdList"),
        13: f("instanced_object_count"),
        14: f("is_unplayed", "bool"),
        16: f("gameplay_data", "message", message="GameplayHouseholdData"),
        18: f("description", "string"),
        19: f("last_modified_time"),
        20: f("creator_id"),
        21: f("creator_name", "string"),
        23: f("modifier_id"),
        24: f("modifier_name", "string"),
        26: f("hidden", "bool"),
        27: f("cheats_enabled", "bool"),
        29: f("premade_household_id"),
        31: f("is_player", "bool"),
        32: f("premade_household_template_id"),
    },
    "ZoneData": {
        1: f("zone_id"),
        2: f("name", "string"),
        3: f("world_id"),
        4: f("lot_id"),
        5: f("lot_template_id"),
        6: f("household_id"),
        7: f("nucleus_id"),
        10: f("neighborhood_id"),
        12: f("lot_description_id"),
        14: f("description", "string"),
    },
    "GameplayData": {
        2: f("daily_sim_info_creation_count"),
    },
    "IdList": {
        1: f("ids", "fixed64", repeated=True),
    },
    # ------------------------------------------------------------------
    # Tray household container (FamilyData inside .householdbinary)
    # ------------------------------------------------------------------
    "FamilyData": {
        1: f("family_account", "message", message="AccountFamilyData"),
        2: f("lastplayed_idx"),
        3: f("lastplayed_simid"),
        4: f("lastplayed_simtime", "float"),
        5: f("homezone_id"),
    },
    "AccountFamilyData": {
        1: f("accountid"),
        2: f("familyid"),
        3: f("familyname", "string"),
        4: f("money"),
        5: f("dirty", "bool"),
        6: f("sim", "message", repeated=True, message="SimData"),
        7: f("responsecode"),
        8: f("familyzoneid"),
        9: f("is_npc", "bool"),
        10: f("is_new", "bool"),
        11: f("description", "string"),
        13: f("last_modified_time"),
        19: f("hashtag_description", "string"),
    },
    # ------------------------------------------------------------------
    # .trayitem metadata
    # ------------------------------------------------------------------
    "TrayItem": {
        1: f("item_id"),
        2: f("item_type"),
        3: f("hash", "bytes"),
        4: f("title", "string"),
        5: f("description", "string"),
        6: f("timestamp"),
        7: f("creator", "string"),
        8: f("flag_8"),
        9: f("flag_9"),
        10: f("data", "message", message="TrayItemData"),
        11: f("household_id"),
        12: f("sim_id_bytes", "bytes"),
        26: f("flag_26"),
        28: f("flag_28"),
        32: f("flag_32"),
        34: f("flag_34"),
    },
    "TrayItemData": {
        2: f("sim_entries", "bytes", repeated=True),
        8: f("tags", "string"),
        10: f("flag_10"),
        11: f("flag_11"),
        12: f("flag_12"),
        18: f("timestamp"),
        20: f("flag_20"),
        21: f("flag_21"),
        23: f("flag_23"),
        24: f("thumbnail_bytes", "bytes"),
        25: f("flag_25"),
        27: f("thumbnail_bytes_2", "bytes"),
        1001: f("build"),
    },
    # ------------------------------------------------------------------
    # Sim header + trackers
    # ------------------------------------------------------------------
    "SimData": {
        1: f("sim_id"),
        2: f("zone_id"),
        3: f("world_id"),
        4: f("household_id"),
        5: f("first_name", "string"),
        6: f("last_name", "string"),
        7: f("gender"),
        8: f("age"),
        9: f("voice_pitch", "float"),
        10: f("skin_tone"),
        11: f("voice_actor"),
        12: f("physique", "string"),
        13: f("age_progress", "float"),
        15: f("significant_other"),
        19: f("created"),
        22: f("household_name", "string"),
        23: f("nucleus_id"),
        25: f("zone_name", "string"),
        27: f("money"),
        29: f("flags"),
        30: f("attributes", "message", message="PersistableSimInfoAttributes"),
        31: f("revision"),
        34: f("primary_aspiration"),
        41: f("current_mood"),
        42: f("current_mood_intensity"),
        45: f("level"),
        47: f("gameplay_data", "message", message="GameplaySimData"),
        48: f("pregnancy_progress", "float"),
        49: f("full_name_key"),
        50: f("last_inzone_outfit_type"),
        51: f("last_inzone_outfit_index"),
        53: f("initial_fitness_value", "float"),
        54: f("voice_effect"),
        55: f("first_name_key"),
        56: f("last_name_key"),
        57: f("generation"),
        60: f("extended_species"),
        61: f("sim_lod"),
        64: f("breed_name", "string"),
        65: f("breed_name_key"),
        66: f("age_progress_randomized", "bool"),
        67: f("skin_tone_val_shift", "float"),
        68: f("fiance"),
        70: f("fix_traits_knowledge", "bool"),
        71: f("needs_age_progress_randomized", "bool"),
    },
    "PersistableSimInfoAttributes": {
        1: f("relationship_tracker", "message", message="PersistableRelationshipTracker"),
        3: f("statistics_tracker", "message", message="PersistableStatisticsTracker"),
        6: f("event_data_tracker", "message", message="PersistableEventDataTracker"),
        7: f("death_tracker", "message", message="PersistableDeathTracker"),
        8: f("pregnancy_tracker", "message", message="PersistablePregnancyTracker"),
        10: f("trait_tracker", "message", message="PersistableTraitTracker"),
        12: f("sim_careers", "message", message="PersistableSimCareers"),
        13: f("skill_tracker", "message", message="PersistableSkillTracker"),
        14: f("genealogy_tracker", "message", message="PersistableGenealogyTracker"),
        17: f("occult_tracker", "message", message="PersistableOccultTracker"),
        29: f("favorites_tracker", "message", message="PersistableFavoritesTracker"),
        30: f("degree_tracker", "message", message="PersistableDegreeTracker"),
        33: f("trait_statistic_tracker", "message", message="PersistableTraitStatisticTracker"),
    },
    "GameplaySimData": {
        17: f("creation_source_data", "string"),
        20: f("premade_sim_template_id"),
        23: f("creation_source"),
        24: f("gameplay_options"),
        27: f(
            "developmental_milestone_tracker",
            "message",
            message="DevelopmentalMilestoneTrackerData",
        ),
        28: f("premade_sim_fixup_completed", "bool"),
    },
    "DevelopmentalMilestoneTrackerData": {
        1: f("active_milestones", "message", repeated=True, message="DevelopmentalMilestoneData"),
        2: f("initial_loot_applied", "bool"),
        3: f("archived_milestones", "message", repeated=True, message="DevelopmentalMilestoneData"),
    },
    "DevelopmentalMilestoneData": {
        1: f("milestone_id"),
        2: f("state"),
        4: f("new_in_ui", "bool"),
        6: f("age_completed"),
    },
    "GameplayHouseholdData": {
        22: f("home_world_id"),
        23: f("last_played_home_zone_id"),
        27: f(
            "household_milestone_tracker",
            "message",
            message="HouseholdMilestoneDataTracker",
        ),
    },
    "HouseholdMilestoneDataTracker": {
        1: f("milestones_completed", repeated=True),
        2: f("objectives_completed", repeated=True),
        4: f(
            "milestone_completion_counts",
            "message",
            repeated=True,
            message="MilestoneCompletionCount",
        ),
    },
    # ------------------------------------------------------------------
    # trait / career / skill / statistics trackers
    # ------------------------------------------------------------------
    "PersistableTraitTracker": {
        1: f("trait_ids", repeated=True),
    },
    "PersistableRelationshipTracker": {
        1: f("relationships", "message", repeated=True, message="PersistableRelationship"),
    },
    "PersistableRelationship": {
        1: f("target_id"),
        2: f("value", "float"),
        3: f("bits", repeated=True),
        5: f(
            "tracks",
            "message",
            repeated=True,
            message="PersistableRelationshipTrack",
        ),
        8: f("last_update_time"),
    },
    "PersistableRelationshipTrack": {
        1: f("track_id"),
        2: f("value", "float"),
        3: f("visible", "bool"),
        4: f("ticks_until_decay_begins", "float"),
    },
    "PersistableSimCareers": {
        1: f("careers", "message", repeated=True, message="PersistableSimCareer"),
        2: f(
            "career_history",
            "message",
            repeated=True,
            message="CareerHistoryEntry",
        ),
    },
    "PersistableSimCareer": {
        1: f("career_uid"),
        2: f("track_uid"),
        3: f("track_level"),
        4: f("user_display_level"),
        6: f("base_work_performance", "float"),
        7: f("positive_work_performance", "float"),
        8: f("negative_work_performance", "float"),
        9: f("company_name_hash"),
        16: f("pending_promotion", "bool"),
        24: f("zone_id"),
        31: f("fame_moment_completed", "bool"),
        40: f("follow_enabled", "bool"),
        42: f("workplace_rival_id"),
    },
    "CareerHistoryEntry": {
        1: f("career_uid"),
        2: f("track_uid"),
        3: f("track_level"),
        4: f("user_display_level"),
        6: f("highest_level"),
        7: f("overmax_level"),
        8: f("daily_pay"),
        9: f("days_worked"),
        10: f("active_days_worked"),
    },
    "PersistableSkillTracker": {
        1: f("skills", "message", repeated=True, message="Skill"),
    },
    "Skill": {
        1: f("name_hash"),
        2: f("value", "float"),
        3: f("level_0_buffer_full", "bool"),
        4: f("time_of_last_value_change"),
    },
    "PersistableStatisticsTracker": {
        1: f("statistics", "message", repeated=True, message="Statistic"),
    },
    "Statistic": {
        1: f("name_hash"),
        2: f("value", "float"),
    },
    "PersistableTraitStatisticTracker": {
        1: f(
            "trait_statistics",
            "message",
            repeated=True,
            message="TraitStatistic",
        ),
    },
    "TraitStatistic": {
        1: f("trait_statistic_id"),
        2: f("value", "float"),
        3: f("state"),
    },
    # ------------------------------------------------------------------
    # aspirations, milestones, genealogy, occult, pregnancy, favorites
    # ------------------------------------------------------------------
    "PersistableEventDataTracker": {
        1: f("milestones_completed", repeated=True),
        2: f("objectives_completed", repeated=True),
        4: f("unlocked_hidden_aspiration_tracks", repeated=True),
        5: f("timed_aspirations", "message", repeated=True, message="TimedAspiration"),
        6: f(
            "milestone_completion_counts",
            "message",
            repeated=True,
            message="MilestoneCompletionCount",
        ),
        7: f(
            "additional_objectives",
            "message",
            repeated=True,
            message="AdditionalObjectives",
        ),
    },
    "TimedAspiration": {
        5: f("aspiration"),
        6: f("end_time"),
        7: f("completed", "bool"),
    },
    "MilestoneCompletionCount": {
        1: f("milestone_guid"),
        2: f("completion_count"),
    },
    "AdditionalObjectives": {
        1: f("milestone_guid"),
        2: f("objective_guids"),
    },
    "PersistableGenealogyTracker": {
        1: f("family_relations", "message", repeated=True, message="FamilyRelation"),
        2: f("relationship_tropes", "message", repeated=True, message="RelationshipTrope"),
    },
    "FamilyRelation": {
        1: f("relation_type"),
        2: f("sim_id"),
    },
    "RelationshipTrope": {
        1: f("sim_id"),
        2: f("trope_id"),
    },
    "PersistablePregnancyTracker": {
        1: f("deprecated_seed", "float"),
        2: f("parent_ids", "fixed64", repeated=True),
        3: f("last_modified"),
        4: f("seed"),
        5: f("origin"),
    },
    "PersistableOccultTracker": {
        1: f("occult_types"),
        2: f("current_occult_types"),
        4: f("pending_occult_type"),
        5: f("occult_form_available", "bool"),
    },
    "PersistableFavoritesTracker": {
        1: f("favorites", "message", repeated=True, message="FavoritesData"),
    },
    "FavoritesData": {
        1: f("favorite_type"),
        2: f("favorite_id"),
        3: f("favorite_def_id"),
    },
    "PersistableDegreeTracker": {
        1: f("current_major"),
        2: f("current_university"),
        3: f("current_credits", "int"),
        4: f("total_gradepoints", "float"),
        5: f("total_courses", "int"),
        10: f("enrollment_status", "int"),
        11: f("end_of_term_time"),
        12: f("reenrollment_time"),
    },
    "PersistableDeathTracker": {
        1: f("death_type"),
        2: f("death_time"),
    },
}
