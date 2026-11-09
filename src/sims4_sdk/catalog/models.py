"""Data models for the static (save-independent) Sims 4 catalog.

Everything here is derived from game/DLC/mod packages only.  No save file is
required to build a :class:`Catalog` or to extract the pre-made Sims that ship
with the game.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "TuningSource",
    "Trait",
    "Preference",
    "Aspiration",
    "AspirationTrack",
    "AspirationCategory",
    "Career",
    "CareerTrack",
    "CareerLevel",
    "SkillLevel",
    "Milestone",
    "RelationshipBit",
    "Catalog",
]


@dataclass(frozen=True)
class TuningSource:
    """Where a definition came from."""

    package: str
    pack: str
    is_mod: bool = False

    @property
    def label(self) -> str:
        if self.is_mod:
            return f"MOD:{self.package}"
        return self.pack


@dataclass
class Trait:
    """A trait tuning entry (personality, occult, ghost, walk style, ...)."""

    id: int
    name: str
    display_name: str
    description: Optional[str]
    trait_type: str
    ages: list[str] = field(default_factory=list)
    species: list[str] = field(default_factory=list)
    occults: list[str] = field(default_factory=list)
    ui_category: Optional[str] = None
    is_hidden: bool = False
    icon: Optional[str] = None
    conflicting_trait_ids: list[int] = field(default_factory=list)
    source: Optional[TuningSource] = None

    @property
    def is_personality(self) -> bool:
        return self.trait_type == "PERSONALITY"

    def __repr__(self) -> str:
        return f"Trait({self.name!r}, type={self.trait_type!r})"


@dataclass
class Preference:
    """A like / dislike tuning entry (``traits.preference``)."""

    id: int
    name: str
    display_name: str
    description: Optional[str]
    preference_type: str
    item: Optional[str] = None
    ages: list[str] = field(default_factory=list)
    species: list[str] = field(default_factory=list)
    conflicting_trait_ids: list[int] = field(default_factory=list)
    source: Optional[TuningSource] = None

    @property
    def is_like(self) -> bool:
        return self.preference_type.upper() in {"LIKE", "LIKES", "LIKED"}

    @property
    def is_dislike(self) -> bool:
        return self.preference_type.upper() in {"DISLIKE", "DISLIKES"}

    def __repr__(self) -> str:
        return f"Preference({self.name!r}, type={self.preference_type!r})"


@dataclass
class AspirationCategory:
    id: int
    name: str
    display_name: str
    sort_order: Optional[int] = None
    source: Optional[TuningSource] = None


@dataclass
class AspirationTrack:
    id: int
    name: str
    display_name: str
    description: Optional[str]
    category_id: Optional[int] = None
    aspiration_ids: list[int] = field(default_factory=list)
    primary_trait_id: Optional[int] = None
    reward_id: Optional[int] = None
    icon: Optional[str] = None
    source: Optional[TuningSource] = None


@dataclass
class Aspiration:
    id: int
    name: str
    display_name: str
    description: Optional[str]
    track_id: Optional[int] = None
    category_id: Optional[int] = None
    valid_ages: list[str] = field(default_factory=list)
    objective_ids: list[int] = field(default_factory=list)
    primary_trait_id: Optional[int] = None
    icon: Optional[str] = None
    source: Optional[TuningSource] = None

    def __repr__(self) -> str:
        return f"Aspiration({self.name!r}, display={self.display_name!r})"


@dataclass
class CareerTrack:
    id: int
    name: str
    display_name: str
    description: Optional[str]
    level_ids: list[int] = field(default_factory=list)
    icon: Optional[str] = None
    source: Optional[TuningSource] = None


@dataclass
class CareerLevel:
    id: int
    name: str
    title: str
    description: Optional[str]
    track_id: Optional[int] = None
    level: Optional[int] = None
    pay_per_hour: Optional[int] = None
    pay_type: Optional[str] = None
    aspiration_id: Optional[int] = None
    promotion_reward_id: Optional[int] = None
    work_days: list[str] = field(default_factory=list)
    work_start_time: Optional[int] = None
    work_duration: Optional[int] = None
    source: Optional[TuningSource] = None

    def __repr__(self) -> str:
        return f"CareerLevel({self.name!r}, title={self.title!r})"


@dataclass
class Career:
    id: int
    name: str
    start_track_id: Optional[int] = None
    track_ids: list[int] = field(default_factory=list)
    category: Optional[str] = None
    source: Optional[TuningSource] = None


@dataclass
class Milestone:
    id: int
    name: str
    display_name: str
    description: Optional[str]
    category: Optional[str] = None
    ages: list[str] = field(default_factory=list)
    repeatable: bool = False
    is_primary: bool = False
    goal_id: Optional[int] = None
    icon: Optional[str] = None
    unlocked_text: Optional[str] = None
    source: Optional[TuningSource] = None

    def __repr__(self) -> str:
        return f"Milestone({self.name!r}, display={self.display_name!r})"


@dataclass
class RelationshipBit:
    id: int
    name: str
    display_name: str
    description: Optional[str]
    depth: Optional[int] = None
    visible: bool = True
    icon: Optional[str] = None
    triggered_track_id: Optional[int] = None
    source: Optional[TuningSource] = None


@dataclass
class SkillLevel:
    """A skill value assigned to a pre-made Sim.

    ``level``/``min_value``/``max_value``/``ideal_value`` come from tuning
    templates.  ``value`` is the raw numeric skill value found in starter-save
    household resources (``0xB3C438F0``); converting it to a level needs the
    skill threshold table, which is not modelled yet.
    """

    skill_id: int
    skill_name: Optional[str] = None
    level: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    ideal_value: Optional[int] = None
    value: Optional[float] = None


@dataclass
class Catalog:
    """All static definitions extracted from the installed game and mods."""

    traits: dict[int, Trait] = field(default_factory=dict)
    preferences: dict[int, Preference] = field(default_factory=dict)
    aspirations: dict[int, Aspiration] = field(default_factory=dict)
    aspiration_tracks: dict[int, AspirationTrack] = field(default_factory=dict)
    aspiration_categories: dict[int, AspirationCategory] = field(default_factory=dict)
    careers: dict[int, Career] = field(default_factory=dict)
    career_tracks: dict[int, CareerTrack] = field(default_factory=dict)
    career_levels: dict[int, CareerLevel] = field(default_factory=dict)
    milestones: dict[int, Milestone] = field(default_factory=dict)
    relationship_bits: dict[int, RelationshipBit] = field(default_factory=dict)
    strings: dict[int, str] = field(default_factory=dict)
    tuning_names: dict[int, str] = field(default_factory=dict, repr=False)
    tuning_classes: dict[int, str] = field(default_factory=dict, repr=False)
    errors: list[str] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # name indexes (built after construction; excluded from repr)
    # ------------------------------------------------------------------
    traits_by_name: dict[str, Trait] = field(default_factory=dict, repr=False)
    preferences_by_name: dict[str, Preference] = field(default_factory=dict, repr=False)
    aspirations_by_name: dict[str, Aspiration] = field(default_factory=dict, repr=False)
    careers_by_name: dict[str, Career] = field(default_factory=dict, repr=False)
    career_levels_by_name: dict[str, CareerLevel] = field(default_factory=dict, repr=False)
    milestones_by_name: dict[str, Milestone] = field(default_factory=dict, repr=False)

    def finalize(self) -> "Catalog":
        """Rebuild name indexes and cross-links."""
        self.traits_by_name = {item.name: item for item in self.traits.values()}
        self.preferences_by_name = {item.name: item for item in self.preferences.values()}
        self.aspirations_by_name = {item.name: item for item in self.aspirations.values()}
        self.careers_by_name = {item.name: item for item in self.careers.values()}
        self.career_levels_by_name = {
            item.name: item for item in self.career_levels.values()
        }
        self.milestones_by_name = {item.name: item for item in self.milestones.values()}

        # Link aspirations to their tracks / categories.
        for track in self.aspiration_tracks.values():
            for aspiration_id in track.aspiration_ids:
                aspiration = self.aspirations.get(aspiration_id)
                if aspiration is not None:
                    aspiration.track_id = track.id
                    aspiration.category_id = track.category_id
                    if aspiration.primary_trait_id is None:
                        aspiration.primary_trait_id = track.primary_trait_id

        # Link career levels to their tracks and infer level numbers.
        for track in self.career_tracks.values():
            for index, level_id in enumerate(track.level_ids, start=1):
                level = self.career_levels.get(level_id)
                if level is not None:
                    level.track_id = track.id
                    if level.level is None:
                        level.level = index
        return self

    # ------------------------------------------------------------------
    # convenience lookups
    # ------------------------------------------------------------------
    def trait(self, key: int | str) -> Optional[Trait]:
        if isinstance(key, int):
            return self.traits.get(key)
        return self.traits_by_name.get(key)

    def preference(self, key: int | str) -> Optional[Preference]:
        if isinstance(key, int):
            return self.preferences.get(key)
        return self.preferences_by_name.get(key)

    def aspiration(self, key: int | str) -> Optional[Aspiration]:
        if isinstance(key, int):
            return self.aspirations.get(key)
        return self.aspirations_by_name.get(key)

    def career(self, key: int | str) -> Optional[Career]:
        if isinstance(key, int):
            return self.careers.get(key)
        return self.careers_by_name.get(key)

    def career_level(self, key: int | str) -> Optional[CareerLevel]:
        if isinstance(key, int):
            return self.career_levels.get(key)
        return self.career_levels_by_name.get(key)

    def milestone(self, key: int | str) -> Optional[Milestone]:
        if isinstance(key, int):
            return self.milestones.get(key)
        return self.milestones_by_name.get(key)

    def resolve_string(self, value: Optional[str]) -> Optional[str]:
        """Resolve a ``0x...`` localization key against the merged STBL."""
        if value is None:
            return None
        text = value.strip()
        if text.lower().startswith("0x"):
            try:
                return self.strings.get(int(text, 16))
            except ValueError:
                return value
        return value

    def summary(self) -> str:
        return (
            f"Catalog(traits={len(self.traits)}, preferences={len(self.preferences)}, "
            f"aspirations={len(self.aspirations)}, careers={len(self.careers)}, "
            f"career_levels={len(self.career_levels)}, milestones={len(self.milestones)}, "
            f"relationship_bits={len(self.relationship_bits)}, strings={len(self.strings)})"
        )
