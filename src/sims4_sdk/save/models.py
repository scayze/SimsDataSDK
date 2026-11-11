"""Models for save-game and Tray data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..core.dbpf import ResourceKey
from ..catalog.models import (
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    GenderOptions,
    Milestone,
    Preference,
    Trait,
)
from ..export import Serializable
from .artwork import Artwork

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
    "SavedRelationshipTrope",
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


def _exact_name(mapping, attribute: str, key: str):
    needle = key.casefold()
    for value in mapping.values():
        name = getattr(value, attribute, None)
        if name and name.casefold() == needle:
            return value
    return None


@dataclass
class SaveSlot(Serializable):
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
class SaveAccount(Serializable):
    email: Optional[str] = None
    client_version: Optional[str] = None
    save_slot_id: Optional[int] = None
    created: Optional[int] = None
    last_login: Optional[int] = None
    number_of_saves: Optional[int] = None
    number_of_saves_mods: Optional[int] = None
    number_of_saves_script_mods: Optional[int] = None


@dataclass
class SaveZone(Serializable):
    zone_id: int
    name: Optional[str] = None
    world_id: Optional[int] = None
    lot_id: Optional[int] = None
    household_id: Optional[int] = None
    neighborhood_id: Optional[int] = None
    description: Optional[str] = None


@dataclass
class SaveNeighborhood(Serializable):
    neighborhood_id: int
    name: Optional[str] = None
    region_id: Optional[int] = None
    description: Optional[str] = None


@dataclass
class SavedSkill(Serializable):
    skill_id: int
    name: Optional[str] = None
    tuning_class: Optional[str] = None
    value: float = 0.0
    level: Optional[int] = None


@dataclass
class SavedCareerHistory(Serializable):
    career_id: int
    track_id: int
    track_level: int
    user_display_level: Optional[int] = None
    highest_level: Optional[int] = None
    daily_pay: Optional[int] = None
    days_worked: Optional[int] = None


@dataclass
class SavedCareer(Serializable):
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
class SavedRelationshipTrack(Serializable):
    track_id: int
    value: float = 0.0
    name: Optional[str] = None
    visible: bool = True


@dataclass
class SavedRelationship(Serializable):
    target_id: int
    target_name: Optional[str] = None
    value: float = 0.0
    bits: list[int] = field(default_factory=list)
    bit_names: list[str] = field(default_factory=list)
    track_values: list[SavedRelationshipTrack] = field(default_factory=list)
    last_update_time: Optional[int] = None


@dataclass
class SavedFamilyRelation(Serializable):
    kind: str
    sim_id: int
    name: Optional[str] = None


@dataclass
class SavedRelationshipTrope(Serializable):
    """A family/romance dynamic stored in the genealogy tracker."""

    sim_id: int
    trope_id: int
    sim_name: Optional[str] = None
    trope_name: Optional[str] = None
    kind: str = "UNKNOWN"  # FAMILY | ROMANCE | UNKNOWN

    def __repr__(self) -> str:
        return (
            f"SavedRelationshipTrope({self.sim_name!r}, "
            f"{self.trope_name!r}, kind={self.kind!r})"
        )


@dataclass
class SavedMilestone(Serializable):
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
class SavedTimedAspiration(Serializable):
    aspiration_id: int
    name: Optional[str] = None
    end_time: Optional[int] = None
    completed: bool = False


@dataclass
class SavedStatistic(Serializable):
    statistic_id: int
    name: Optional[str] = None
    value: float = 0.0


@dataclass
class SavedSim(Serializable):
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
    fiance_name: Optional[str] = None
    steady_ids: list[int] = field(default_factory=list)
    steady_names: list[str] = field(default_factory=list)
    tropes: list[SavedRelationshipTrope] = field(default_factory=list)
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
    def gender_options(self) -> GenderOptions:
        return GenderOptions.from_traits(self.traits)

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
class SavedHousehold(Serializable):
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
class SaveFile(Serializable):
    path: Path
    slot: SaveSlot = field(default_factory=SaveSlot)
    account: SaveAccount = field(default_factory=SaveAccount)
    sims: dict[int, SavedSim] = field(default_factory=dict)
    households: dict[int, SavedHousehold] = field(default_factory=dict)
    zones: dict[int, SaveZone] = field(default_factory=dict)
    neighborhoods: dict[int, SaveNeighborhood] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    artwork: dict[ResourceKey, Artwork] = field(default_factory=dict, repr=False)
    artwork_errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def thumbnail_image(self) -> Optional[Artwork]:
        """The save's instance-zero household thumbnail, if present."""
        return self.artwork.get(ResourceKey(0x14, 0, 0))

    @property
    def thumbnail(self) -> Optional[bytes]:
        image = self.thumbnail_image
        return image.jpeg if image is not None else None

    @property
    def household_artwork(self) -> dict[int, bytes]:
        """Household thumbnails whose instance matches a known household ID.

        Instance-zero thumbnails are available as :attr:`thumbnail_image`;
        they are not assumed to identify a particular household.
        """
        return {
            key.instance: image.jpeg for key, image in self.artwork.items()
            if key.type_id == 0x14 and key.group == 0 and key.instance in self.households
            and key.instance != 0
        }

    @property
    def active_household(self) -> Optional[SavedHousehold]:
        """The household that was active when the save was written."""
        if self.slot.active_household_id is None:
            return None
        return self.households.get(self.slot.active_household_id)

    def household_sims(
        self, household: SavedHousehold | int | str
    ) -> list[SavedSim]:
        """Return the member Sims of a household (in member order)."""
        if not isinstance(household, SavedHousehold):
            household = self.household(household) if household is not None else None
        if household is None:
            return []
        return [
            self.sims[sim_id]
            for sim_id in household.member_ids
            if sim_id in self.sims
        ]

    def sim(self, key: str | int) -> Optional[SavedSim]:
        """Look up a Sim by ID, exact name, or name fragment."""
        if isinstance(key, int):
            return self.sims.get(key)
        exact = _exact_name(self.sims, "full_name", key)
        if exact is not None:
            return exact
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
        """Look up a household by ID, exact name, or name fragment."""
        if isinstance(key, int):
            return self.households.get(key)
        exact = _exact_name(self.households, "name", key)
        if exact is not None:
            return exact
        needle = key.casefold()
        return next(
            (
                household
                for household in self.households.values()
                if household.name and needle in household.name.casefold()
            ),
            None,
        )

    def find_sims(
        self,
        query: str = "",
        *,
        household: str | int | None = None,
        age: Optional[str] = None,
        species: Optional[str] = None,
        occult: Optional[str] = None,
        is_dead: Optional[bool] = None,
    ) -> list[SavedSim]:
        """Filter live Sims by name and/or common attributes."""
        needle = query.casefold()
        household_id: Optional[int] = None
        household_name: Optional[str] = None
        if isinstance(household, int):
            household_id = household
        elif household is not None:
            household_name = household.casefold()

        results: list[SavedSim] = []
        for sim in self.sims.values():
            if needle and needle not in sim.full_name.casefold():
                continue
            if household_id is not None and sim.household_id != household_id:
                continue
            if household_name is not None and (
                (sim.household_name or "").casefold() != household_name
            ):
                continue
            if age and (sim.age or "").casefold() != age.casefold():
                continue
            if species and (sim.species or "").casefold() != species.casefold():
                continue
            if occult and occult.casefold() not in {item.casefold() for item in sim.occult}:
                continue
            if is_dead is not None and sim.is_dead != is_dead:
                continue
            results.append(sim)
        return results

    def find_households(
        self,
        query: str = "",
        *,
        is_player: Optional[bool] = None,
        is_unplayed: Optional[bool] = None,
    ) -> list[SavedHousehold]:
        needle = query.casefold()
        results: list[SavedHousehold] = []
        for household in self.households.values():
            if needle and needle not in (household.name or "").casefold():
                continue
            if is_player is not None and household.is_player != is_player:
                continue
            if is_unplayed is not None and household.is_unplayed != is_unplayed:
                continue
            results.append(household)
        return results

    def summary(self) -> str:
        return (
            f"SaveFile({self.slot.slot_name!r}, sims={len(self.sims)}, "
            f"households={len(self.households)}, zones={len(self.zones)})"
        )


# ----------------------------------------------------------------------
# Tray
# ----------------------------------------------------------------------
@dataclass
class TrayItem(Serializable):
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
class TrayHousehold(Serializable):
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

    def household_images(self) -> list[Artwork]:
        """Read all matching household image variants on demand."""
        from .tray import _image_paths
        from .artwork import read_tray_image

        try:
            instance = int(self.path.stem.split("!")[-1], 0)
        except ValueError:
            return []
        return [read_tray_image(path) for path in _image_paths(self.path.parent, "hhi", instance)]

    def household_image(self) -> Optional[Artwork]:
        """Return the highest-resolution household variant, if present."""
        return max(self.household_images(), key=_image_area, default=None)

    def portrait(self, sim_id: int) -> Optional[Artwork]:
        """Read a household member's matching Sim portrait, if present."""
        from .tray import _image_paths
        from .artwork import read_tray_image

        if not any(sim.sim_id == sim_id for sim in self.sims):
            return None
        images = (read_tray_image(path) for path in _image_paths(self.path.parent, "sgi", sim_id))
        return max(images, key=_image_area, default=None)

    def __repr__(self) -> str:
        return f"TrayHousehold({self.family_name!r}, sims={len(self.sims)})"


def _image_area(image: Artwork) -> int:
    return (image.width or 0) * (image.height or 0)


@dataclass
class TrayLibrary(Serializable):
    items: list[TrayItem] = field(default_factory=list)
    households: list[TrayHousehold] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def household(self, key: str | int) -> Optional[TrayHousehold]:
        if isinstance(key, int):
            return next((hh for hh in self.households if hh.item and hh.item.item_id == key), None)
        needle = key.casefold()
        exact = next(
            (
                hh
                for hh in self.households
                if (hh.family_name and hh.family_name.casefold() == needle)
                or (
                    hh.item
                    and hh.item.title
                    and hh.item.title.casefold() == needle
                )
            ),
            None,
        )
        if exact is not None:
            return exact
        return next(
            (
                hh
                for hh in self.households
                if (hh.family_name and needle in hh.family_name.casefold())
                or (hh.item and hh.item.title and needle in hh.item.title.casefold())
            ),
            None,
        )

    def find_households(
        self,
        query: str = "",
        *,
        creator: Optional[str] = None,
    ) -> list[TrayHousehold]:
        """Filter Gallery households by family name/title and creator."""
        needle = query.casefold()
        results: list[TrayHousehold] = []
        for household in self.households:
            title = household.item.title if household.item else None
            if needle and needle not in (household.family_name or "").casefold() and needle not in (title or "").casefold():
                continue
            if creator:
                actual = household.item.creator if household.item else None
                if (actual or "").casefold() != creator.casefold():
                    continue
            results.append(household)
        return results

    def find_sims(self, query: str = "") -> list[SavedSim]:
        """Return every Tray Sim whose name contains ``query``."""
        needle = query.casefold()
        return [
            sim
            for household in self.households
            for sim in household.sims
            if not needle or needle in sim.full_name.casefold()
        ]

    def summary(self) -> str:
        return f"TrayLibrary(items={len(self.items)}, households={len(self.households)})"
