"""Models for save-game and Tray data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..catalog.models import (
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Milestone,
    Preference,
    Trait,
)

__all__ = [
    "SaveSlot",
    "SaveAccount",
    "SaveZone",
    "SaveNeighborhood",
    "SavedSkill",
    "SavedCareerHistory",
    "SavedCareer",
    "SavedRelationshipTrack",
    "SavedRelationship",
    "SavedFamilyRelation",
    "SavedMilestone",
    "SavedTimedAspiration",
    "SavedStatistic",
    "SavedSim",
    "SavedHousehold",
    "SaveFile",
    "TrayItem",
    "TrayHousehold",
    "TrayLibrary",
]


@dataclass
class SaveSlot:
    slot_id: Optional[int] = None
    slot_name: Optional[str] = None
    timestamp: Optional[int] = None
    active_household_id: Optional[int] = None
    nucleus_id: Optional[int] = None
    s4_guid_seed: Optional[int] = None
    compatibility_version: Optional[int] = None
    last_neighborhood: Optional[int] = None
    last_zone: Optional[int] = None


@dataclass
class SaveAccount:
    email: Optional[str] = None
    client_version: Optional[str] = None
    save_slot_id: Optional[int] = None
    created: Optional[int] = None
    last_login: Optional[int] = None
    number_of_saves: Optional[int] = None
    number_of_saves_mods: Optional[int] = None
    number_of_saves_script_mods: Optional[int] = None


@dataclass
class SaveZone:
    zone_id: int
    name: Optional[str] = None
    world_id: Optional[int] = None
    lot_id: Optional[int] = None
    household_id: Optional[int] = None
    neighborhood_id: Optional[int] = None
    description: Optional[str] = None


@dataclass
class SaveNeighborhood:
    neighborhood_id: int
    name: Optional[str] = None
    region_id: Optional[int] = None
    description: Optional[str] = None


@dataclass
class SavedSkill:
    skill_id: int
    name: Optional[str] = None
    tuning_class: Optional[str] = None
    value: float = 0.0
    level: Optional[int] = None


@dataclass
class SavedCareerHistory:
    career_id: int
    track_id: int
    track_level: int
    user_display_level: Optional[int] = None
    highest_level: Optional[int] = None
    daily_pay: Optional[int] = None
    days_worked: Optional[int] = None


@dataclass
class SavedCareer:
    career_id: int
    track_id: int
    track_level: int
    career: Optional[Career] = None
    track: Optional[CareerTrack] = None
    level_id: Optional[int] = None
    level: Optional[CareerLevel] = None
    user_display_level: Optional[int] = None
    pay_per_hour: Optional[int] = None
    pending_promotion: bool = False
    base_performance: Optional[float] = None
    positive_performance: Optional[float] = None
    negative_performance: Optional[float] = None
    history: list[SavedCareerHistory] = field(default_factory=list)

    @property
    def title(self) -> Optional[str]:
        return self.level.title if self.level is not None else None

    @property
    def career_name(self) -> Optional[str]:
        return self.career.name if self.career is not None else None

    @property
    def track_name(self) -> Optional[str]:
        return self.track.display_name if self.track is not None else None


@dataclass
class SavedRelationshipTrack:
    track_id: int
    value: float = 0.0
    name: Optional[str] = None
    visible: bool = True


@dataclass
class SavedRelationship:
    target_id: int
    target_name: Optional[str] = None
    value: float = 0.0
    bits: list[int] = field(default_factory=list)
    bit_names: list[str] = field(default_factory=list)
    track_values: list[SavedRelationshipTrack] = field(default_factory=list)
    last_update_time: Optional[int] = None


@dataclass
class SavedFamilyRelation:
    kind: str
    sim_id: int
    name: Optional[str] = None


@dataclass
class SavedMilestone:
    milestone_id: int
    milestone: Optional[Milestone] = None
    state: Optional[int] = None
    age_completed: Optional[int] = None
    new_in_ui: bool = False

    @property
    def name(self) -> Optional[str]:
        return self.milestone.name if self.milestone is not None else None

    @property
    def display_name(self) -> Optional[str]:
        return self.milestone.display_name if self.milestone is not None else None


@dataclass
class SavedTimedAspiration:
    aspiration_id: int
    name: Optional[str] = None
    end_time: Optional[int] = None
    completed: bool = False


@dataclass
class SavedStatistic:
    statistic_id: int
    name: Optional[str] = None
    value: float = 0.0


@dataclass
class SavedSim:
    sim_id: int
    first_name: str = ""
    last_name: str = ""
    nucleus_id: Optional[int] = None
    household_id: Optional[int] = None
    household_name: Optional[str] = None
    zone_id: Optional[int] = None
    world_id: Optional[int] = None

    age_raw: Optional[int] = None
    age: Optional[str] = None
    gender_raw: Optional[int] = None
    gender: Optional[str] = None
    species_raw: Optional[int] = None
    species: Optional[str] = None
    occult_raw: int = 0
    occult: list[str] = field(default_factory=list)
    pronouns: Optional[str] = None

    primary_aspiration_track_id: Optional[int] = None
    aspiration_track: Optional[AspirationTrack] = None

    traits: list[Trait] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    unknown_trait_ids: list[int] = field(default_factory=list)
    careers: list[SavedCareer] = field(default_factory=list)
    skills: list[SavedSkill] = field(default_factory=list)
    relationships: list[SavedRelationship] = field(default_factory=list)

    spouse_id: Optional[int] = None
    spouse_name: Optional[str] = None
    fiance_id: Optional[int] = None
    parents: list[SavedFamilyRelation] = field(default_factory=list)
    children: list[SavedFamilyRelation] = field(default_factory=list)
    siblings: list[SavedFamilyRelation] = field(default_factory=list)
    extended_family: list[SavedFamilyRelation] = field(default_factory=list)

    milestones: list[SavedMilestone] = field(default_factory=list)
    objective_ids: list[int] = field(default_factory=list)
    completed_milestone_ids: list[int] = field(default_factory=list)
    timed_aspirations: list[SavedTimedAspiration] = field(default_factory=list)

    pregnancy: dict[str, Any] = field(default_factory=dict)
    degree: dict[str, Any] = field(default_factory=dict)
    death: dict[str, Any] = field(default_factory=dict)
    favorites: list[dict[str, Any]] = field(default_factory=list)
    statistics: list[SavedStatistic] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_dead(self) -> bool:
        return bool(self.death.get("death_type")) or bool(self.death.get("death_time"))

    @property
    def personality_traits(self) -> list[Trait]:
        return [trait for trait in self.traits if trait.trait_type == "PERSONALITY"]

    @property
    def hidden_traits(self) -> list[Trait]:
        return [trait for trait in self.traits if trait.is_hidden]

    @property
    def visible_traits(self) -> list[Trait]:
        internal = {
            "HIDDEN",
            "GENDER_OPTIONS",
            "WALKSTYLE",
            "TAILSTYLE",
            "SIM_PHONE",
            "AGENT",
            "SPECIES",
            "AGE",
        }
        return [trait for trait in self.traits if trait.trait_type not in internal]

    @property
    def likes(self) -> list[Preference]:
        return [preference for preference in self.preferences if preference.is_like]

    @property
    def dislikes(self) -> list[Preference]:
        return [preference for preference in self.preferences if preference.is_dislike]

    @property
    def career(self) -> Optional[SavedCareer]:
        return self.careers[0] if self.careers else None

    def __repr__(self) -> str:
        return f"SavedSim({self.full_name!r}, id={self.sim_id}, age={self.age!r})"


@dataclass
class SavedHousehold:
    household_id: int
    name: Optional[str] = None
    money: Optional[int] = None
    home_zone: Optional[int] = None
    last_played_sim_id: Optional[int] = None
    creation_time: Optional[int] = None
    last_modified_time: Optional[int] = None
    is_unplayed: bool = False
    is_player: bool = False
    hidden: bool = False
    premade_household_id: Optional[int] = None
    premade_household_template_id: Optional[int] = None
    description: Optional[str] = None
    member_ids: list[int] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    milestones_completed: list[int] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __repr__(self) -> str:
        return f"SavedHousehold({self.name!r}, members={len(self.member_ids)})"


@dataclass
class SaveFile:
    path: Path
    slot: SaveSlot = field(default_factory=SaveSlot)
    account: SaveAccount = field(default_factory=SaveAccount)
    sims: dict[int, SavedSim] = field(default_factory=dict)
    households: dict[int, SavedHousehold] = field(default_factory=dict)
    zones: dict[int, SaveZone] = field(default_factory=dict)
    neighborhoods: dict[int, SaveNeighborhood] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def sim(self, key: str | int) -> Optional[SavedSim]:
        if isinstance(key, int):
            return self.sims.get(key)
        needle = key.casefold()
        return next(
            (
                sim
                for sim in self.sims.values()
                if needle in sim.full_name.casefold() or needle in sim.first_name.casefold()
            ),
            None,
        )

    def household(self, key: str | int) -> Optional[SavedHousehold]:
        if isinstance(key, int):
            return self.households.get(key)
        needle = key.casefold()
        return next(
            (
                household
                for household in self.households.values()
                if household.name and needle in household.name.casefold()
            ),
            None,
        )

    def find_sims(self, query: str) -> list[SavedSim]:
        needle = query.casefold()
        return [
            sim
            for sim in self.sims.values()
            if needle in sim.full_name.casefold()
        ]

    def summary(self) -> str:
        return (
            f"SaveFile({self.slot.slot_name!r}, sims={len(self.sims)}, "
            f"households={len(self.households)}, zones={len(self.zones)})"
        )


# ----------------------------------------------------------------------
# Tray
# ----------------------------------------------------------------------
@dataclass
class TrayItem:
    path: Path
    item_id: Optional[int] = None
    item_type: Optional[int] = None
    hash: Optional[bytes] = None
    title: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    timestamp: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class TrayHousehold:
    path: Path
    item: Optional[TrayItem] = None
    family_name: Optional[str] = None
    description: Optional[str] = None
    money: Optional[int] = None
    home_zone: Optional[int] = None
    last_played_sim_id: Optional[int] = None
    hashtag_description: Optional[str] = None
    sims: list[SavedSim] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __repr__(self) -> str:
        return f"TrayHousehold({self.family_name!r}, sims={len(self.sims)})"


@dataclass
class TrayLibrary:
    items: list[TrayItem] = field(default_factory=list)
    households: list[TrayHousehold] = field(default_factory=list)

    def household(self, key: str | int) -> Optional[TrayHousehold]:
        if isinstance(key, int):
            return next((hh for hh in self.households if hh.item and hh.item.item_id == key), None)
        needle = key.casefold()
        return next(
            (
                hh
                for hh in self.households
                if (hh.family_name and needle in hh.family_name.casefold())
                or (hh.item and hh.item.title and needle in hh.item.title.casefold())
            ),
            None,
        )

    def summary(self) -> str:
        return f"TrayLibrary(items={len(self.items)}, households={len(self.households)})"
