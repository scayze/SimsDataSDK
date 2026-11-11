"""Data models for the static (save-independent) Sims 4 catalog.

Everything here is derived from game/DLC/mod packages only.  No save file is
required to build a :class:`Catalog` or to extract the pre-made Sims that ship
with the game.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from ..core.dbpf import ResourceKey
from ..exceptions import Sims4SDKError
from ..export import Serializable
from .diagnostics import ExtractionIssue

__all__ = [
    "CatalogError",
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
    "RelationshipTrackValue",
    "RelationshipDefault",
    "PremadeRelationship",
    "GenderOptions",
    "Catalog",
]


class CatalogError(Sims4SDKError, ValueError):
    """Raised when a catalog snapshot cannot be saved or loaded."""


def _lookup(mapping: dict[str, object], key: str):
    """Exact name lookup first, then a case-insensitive fallback."""
    item = mapping.get(key)
    if item is not None:
        return item
    needle = key.casefold()
    return next(
        (value for name, value in mapping.items() if name.casefold() == needle),
        None,
    )


def _matches_text(name: Optional[str], display_name: Optional[str], needle: str) -> bool:
    if not needle:
        return True
    return needle in (name or "").casefold() or needle in (display_name or "").casefold()


def _matches_source(source: Optional["TuningSource"], pack: Optional[str]) -> bool:
    if not pack:
        return True
    if source is None:
        return False
    needle = pack.casefold()
    return needle in (source.pack.casefold(), source.label.casefold())


@dataclass(frozen=True)
class TuningSource(Serializable):
    """Where a definition came from."""

    package: str
    pack: str
    is_mod: bool = False
    #: Path of the source package; the key identifies the containing resource.
    path: Optional[str] = None
    resource_key: Optional[ResourceKey] = None

    @property
    def label(self) -> str:
        if self.is_mod:
            return f"MOD:{self.package}"
        return self.pack


@dataclass
class Trait(Serializable):
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

    @property
    def is_internal(self) -> bool:
        """Whether known metadata identifies this as an internal trait.

        This is a conservative classification, not a guarantee that every
        remaining trait is visible or assignable in Create-a-Sim.
        """
        internal_types = {
            "HIDDEN", "GENDER_OPTIONS", "WALKSTYLE", "TAILSTYLE", "SIM_PHONE",
            "AGENT", "SPECIES", "AGE", "PREFERENCE",
        }
        name = self.name.casefold()
        return (
            self.is_hidden
            or self.trait_type.upper() in internal_types
            or name.startswith(("trait_genderoptions_", "trait_sexualorientation_", "trait_species_", "trait_simpreference_"))
            or name in {"trait_genderfemale", "trait_gendermale"}
        )

    def __repr__(self) -> str:
        return f"Trait({self.name!r}, type={self.trait_type!r})"


@dataclass
class Preference(Serializable):
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
class AspirationCategory(Serializable):
    id: int
    name: str
    display_name: str
    sort_order: Optional[int] = None
    source: Optional[TuningSource] = None


@dataclass
class AspirationTrack(Serializable):
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
class Aspiration(Serializable):
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
class CareerTrack(Serializable):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    level_ids: list[int] = field(default_factory=list)
    icon: Optional[str] = None
    source: Optional[TuningSource] = None


@dataclass
class CareerLevel(Serializable):
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
class Career(Serializable):
    id: int
    name: str
    start_track_id: Optional[int] = None
    track_ids: list[int] = field(default_factory=list)
    category: Optional[str] = None
    source: Optional[TuningSource] = None
    #: Localized name of the starting track, when that track is available.
    display_name: Optional[str] = None


@dataclass
class Milestone(Serializable):
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
class RelationshipBit(Serializable):
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
class RelationshipTrackValue(Serializable):
    """One relationship track with a fixed value or a min/max range."""

    track_id: int
    track_name: Optional[str] = None
    value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class RelationshipDefault(Serializable):
    """Default relationship values for a genealogy link (Roommate, Spouse, ...)."""

    link: str
    tracks: list[RelationshipTrackValue] = field(default_factory=list)
    bit_ids: list[int] = field(default_factory=list)
    loot_ids: list[int] = field(default_factory=list)

    def track(self, track_id: int) -> Optional[RelationshipTrackValue]:
        return next((item for item in self.tracks if item.track_id == track_id), None)

    def __repr__(self) -> str:
        return f"RelationshipDefault({self.link!r}, tracks={len(self.tracks)})"


@dataclass
class PremadeRelationship(Serializable):
    """An initial relationship between two pre-made Sims in different households."""

    sim_a: int
    sim_b: int
    tracks: list[RelationshipTrackValue] = field(default_factory=list)
    bit_ids: list[int] = field(default_factory=list)
    sentiment_track_ids: list[int] = field(default_factory=list)
    loot_id: Optional[int] = None
    sim_a_name: Optional[str] = None
    sim_b_name: Optional[str] = None

    def track(self, track_id: int) -> Optional[RelationshipTrackValue]:
        return next((item for item in self.tracks if item.track_id == track_id), None)

    @property
    def friendship(self) -> Optional[float]:
        item = self.track(16650)
        return item.value if item is not None else None

    @property
    def romance(self) -> Optional[float]:
        item = self.track(16651)
        return item.value if item is not None else None

    def __repr__(self) -> str:
        return (
            f"PremadeRelationship({self.sim_a_name or hex(self.sim_a)!r} -> "
            f"{self.sim_b_name or hex(self.sim_b)!r}, "
            f"friendship={self.friendship}, romance={self.romance})"
        )


_GENDER_SINGLE = {
    "trait_genderoptions_frame_masculine": ("frame", "MASCULINE"),
    "trait_genderoptions_frame_feminine": ("frame", "FEMININE"),
    "trait_genderoptions_clothing_menswear": ("clothing", "MENSWEAR"),
    "trait_genderoptions_clothing_womenswear": ("clothing", "WOMENSWEAR"),
    "trait_genderoptions_toilet_standing": ("toilet_use", "STANDING"),
    "trait_genderoptions_toilet_sitting": ("toilet_use", "SITTING"),
    "trait_genderoptions_lactate_can": ("lactation", "CAN"),
    "trait_genderoptions_lactate_cannot": ("lactation", "CANNOT"),
    "trait_genderoptions_sexuality_exploring": ("sexuality", "EXPLORING"),
    "trait_genderoptions_sexuality_notexploring": ("sexuality", "NOT_EXPLORING"),
    "trait_gendermale": ("gender", "MALE"),
    "trait_genderfemale": ("gender", "FEMALE"),
}

_GENDER_LISTS = {
    "trait_genderoptions_attractedto_male": ("attracted_to", "MALE"),
    "trait_genderoptions_attractedto_female": ("attracted_to", "FEMALE"),
    "trait_genderoptions_attractedto_notmale": ("not_attracted_to", "MALE"),
    "trait_genderoptions_attractedto_notfemale": ("not_attracted_to", "FEMALE"),
    "trait_sexualorientation_woohoointerests_male": ("woohoo_interests", "MALE"),
    "trait_sexualorientation_woohoointerests_female": ("woohoo_interests", "FEMALE"),
    "trait_sexualorientation_woohoointerests_notmale": (
        "not_woohoo_interests",
        "MALE",
    ),
    "trait_sexualorientation_woohoointerests_notfemale": (
        "not_woohoo_interests",
        "FEMALE",
    ),
}

_GENDER_BOOLS = {
    "trait_genderoptions_pregnancy_canimpregnate": ("can_impregnate", True),
    "trait_genderoptions_pregnancy_cannotimpregnate": ("can_impregnate", False),
    "trait_genderoptions_pregnancy_canbeimpregnated": ("can_be_impregnated", True),
    "trait_genderoptions_pregnancy_cannot_beimpregnated": (
        "can_be_impregnated",
        False,
    ),
}


@dataclass
class GenderOptions(Serializable):
    """Structured view of the ``trait_GenderOptions_*`` trait family."""

    gender: Optional[str] = None
    frame: Optional[str] = None
    clothing: Optional[str] = None
    toilet_use: Optional[str] = None
    lactation: Optional[str] = None
    attracted_to: list[str] = field(default_factory=list)
    not_attracted_to: list[str] = field(default_factory=list)
    woohoo_interests: list[str] = field(default_factory=list)
    not_woohoo_interests: list[str] = field(default_factory=list)
    sexuality: Optional[str] = None
    can_impregnate: Optional[bool] = None
    can_be_impregnated: Optional[bool] = None

    @classmethod
    def from_traits(cls, traits: Iterable["Trait"]) -> "GenderOptions":
        options = cls()
        for trait in traits:
            key = trait.name.casefold()
            single = _GENDER_SINGLE.get(key)
            if single is not None:
                setattr(options, single[0], single[1])
                continue
            listed = _GENDER_LISTS.get(key)
            if listed is not None:
                values = getattr(options, listed[0])
                if listed[1] not in values:
                    values.append(listed[1])
                continue
            boolean = _GENDER_BOOLS.get(key)
            if boolean is not None:
                setattr(options, boolean[0], boolean[1])
        return options

    def __repr__(self) -> str:
        return (
            f"GenderOptions(gender={self.gender!r}, frame={self.frame!r}, "
            f"clothing={self.clothing!r}, attracted_to={self.attracted_to}, "
            f"woohoo_interests={self.woohoo_interests})"
        )


@dataclass
class SkillLevel(Serializable):
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
class Catalog(Serializable):
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
    relationship_defaults: dict[str, RelationshipDefault] = field(default_factory=dict)
    premade_relationships: list[PremadeRelationship] = field(default_factory=list)
    relationship_track_ranges: dict[int, RelationshipTrackValue] = field(
        default_factory=dict, repr=False
    )
    steady_bit_id: Optional[int] = None
    engagement_bit_id: Optional[int] = None
    marriage_bit_id: Optional[int] = None
    family_trope_ids: list[int] = field(default_factory=list)
    romance_trope_ids: list[int] = field(default_factory=list)
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
    aspiration_tracks_by_name: dict[str, AspirationTrack] = field(
        default_factory=dict, repr=False
    )
    aspiration_categories_by_name: dict[str, AspirationCategory] = field(
        default_factory=dict, repr=False
    )
    careers_by_name: dict[str, Career] = field(default_factory=dict, repr=False)
    career_tracks_by_name: dict[str, CareerTrack] = field(
        default_factory=dict, repr=False
    )
    career_levels_by_name: dict[str, CareerLevel] = field(default_factory=dict, repr=False)
    milestones_by_name: dict[str, Milestone] = field(default_factory=dict, repr=False)
    relationship_bits_by_name: dict[str, RelationshipBit] = field(
        default_factory=dict, repr=False
    )
    diagnostics: list[ExtractionIssue] = field(default_factory=list)

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        if "diagnostics" not in state:
            self.diagnostics = []

    @property
    def visible_traits(self) -> list[Trait]:
        """Traits excluding known internal definitions; not an assignability guarantee."""
        return [
            trait for trait in self.traits.values()
            if not trait.is_internal and trait.id not in self.preferences
        ]

    def finalize(self) -> "Catalog":
        """Rebuild name indexes and cross-links."""
        self.traits_by_name = {item.name: item for item in self.traits.values()}
        self.preferences_by_name = {item.name: item for item in self.preferences.values()}
        self.aspirations_by_name = {item.name: item for item in self.aspirations.values()}
        self.aspiration_tracks_by_name = {
            item.name: item for item in self.aspiration_tracks.values()
        }
        self.aspiration_categories_by_name = {
            item.name: item for item in self.aspiration_categories.values()
        }
        self.careers_by_name = {item.name: item for item in self.careers.values()}
        self.career_tracks_by_name = {
            item.name: item for item in self.career_tracks.values()
        }
        self.career_levels_by_name = {
            item.name: item for item in self.career_levels.values()
        }
        self.milestones_by_name = {item.name: item for item in self.milestones.values()}
        self.relationship_bits_by_name = {
            item.name: item for item in self.relationship_bits.values()
        }

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

        for career in self.careers.values():
            track = self.career_tracks.get(career.start_track_id)
            career.display_name = track.display_name if track is not None else None

        for default in self.relationship_defaults.values():
            for item in default.tracks:
                if item.track_name is None:
                    item.track_name = self.tuning_names.get(item.track_id)
        for relationship in self.premade_relationships:
            for item in relationship.tracks:
                if item.track_name is None:
                    item.track_name = self.tuning_names.get(item.track_id)
        for item in self.relationship_track_ranges.values():
            if item.track_name is None:
                item.track_name = self.tuning_names.get(item.track_id)
        return self

    # ------------------------------------------------------------------
    # convenience lookups
    # ------------------------------------------------------------------
    def trait(self, key: int | str) -> Optional[Trait]:
        if isinstance(key, int):
            return self.traits.get(key)
        return _lookup(self.traits_by_name, key)

    def preference(self, key: int | str) -> Optional[Preference]:
        if isinstance(key, int):
            return self.preferences.get(key)
        return _lookup(self.preferences_by_name, key)

    def aspiration(self, key: int | str) -> Optional[Aspiration]:
        if isinstance(key, int):
            return self.aspirations.get(key)
        return _lookup(self.aspirations_by_name, key)

    def aspiration_track(self, key: int | str) -> Optional[AspirationTrack]:
        if isinstance(key, int):
            return self.aspiration_tracks.get(key)
        return _lookup(self.aspiration_tracks_by_name, key)

    def aspiration_category(self, key: int | str) -> Optional[AspirationCategory]:
        if isinstance(key, int):
            return self.aspiration_categories.get(key)
        return _lookup(self.aspiration_categories_by_name, key)

    def career(self, key: int | str) -> Optional[Career]:
        if isinstance(key, int):
            return self.careers.get(key)
        return _lookup(self.careers_by_name, key)

    def career_track(self, key: int | str) -> Optional[CareerTrack]:
        if isinstance(key, int):
            return self.career_tracks.get(key)
        return _lookup(self.career_tracks_by_name, key)

    def career_level(self, key: int | str) -> Optional[CareerLevel]:
        if isinstance(key, int):
            return self.career_levels.get(key)
        return _lookup(self.career_levels_by_name, key)

    def milestone(self, key: int | str) -> Optional[Milestone]:
        if isinstance(key, int):
            return self.milestones.get(key)
        return _lookup(self.milestones_by_name, key)

    def relationship_bit(self, key: int | str) -> Optional[RelationshipBit]:
        if isinstance(key, int):
            return self.relationship_bits.get(key)
        return _lookup(self.relationship_bits_by_name, key)

    def tuning_name(self, tuning_id: int) -> Optional[str]:
        """Return the tuning name for an arbitrary definition ID."""
        return self.tuning_names.get(tuning_id)

    def tuning_class(self, tuning_id: int) -> Optional[str]:
        """Return the tuning class (``Skill``, ``Statistic``, ...) for an ID."""
        return self.tuning_classes.get(tuning_id)

    # ------------------------------------------------------------------
    # search and filtering
    # ------------------------------------------------------------------
    def find_traits(
        self,
        query: str = "",
        *,
        trait_type: Optional[str] = None,
        pack: Optional[str] = None,
        visible_only: bool = False,
    ) -> list[Trait]:
        """Return traits whose name/display name contain ``query``."""
        needle = query.casefold()
        return [
            item
            for item in self.traits.values()
            if _matches_text(item.name, item.display_name, needle)
            and (
                trait_type is None
                or item.trait_type.casefold() == trait_type.casefold()
            )
            and _matches_source(item.source, pack)
            and not (visible_only and item.is_hidden)
        ]

    def find_preferences(
        self,
        query: str = "",
        *,
        preference_type: Optional[str] = None,
        pack: Optional[str] = None,
    ) -> list[Preference]:
        needle = query.casefold()
        return [
            item
            for item in self.preferences.values()
            if _matches_text(item.name, item.display_name, needle)
            and (
                preference_type is None
                or item.preference_type.casefold() == preference_type.casefold()
            )
            and _matches_source(item.source, pack)
        ]

    def find_aspirations(
        self,
        query: str = "",
        *,
        pack: Optional[str] = None,
    ) -> list[Aspiration]:
        needle = query.casefold()
        return [
            item
            for item in self.aspirations.values()
            if _matches_text(item.name, item.display_name, needle)
            and _matches_source(item.source, pack)
        ]

    def find_careers(
        self,
        query: str = "",
        *,
        pack: Optional[str] = None,
    ) -> list[Career]:
        needle = query.casefold()
        return [
            item
            for item in self.careers.values()
            if _matches_text(item.name, None, needle)
            and _matches_source(item.source, pack)
        ]

    def find_milestones(
        self,
        query: str = "",
        *,
        category: Optional[str] = None,
        pack: Optional[str] = None,
    ) -> list[Milestone]:
        needle = query.casefold()
        return [
            item
            for item in self.milestones.values()
            if _matches_text(item.name, item.display_name, needle)
            and (
                category is None
                or (item.category or "").casefold() == category.casefold()
            )
            and _matches_source(item.source, pack)
        ]

    def packs(self) -> list[str]:
        """Return the sorted labels of every pack/mod present in the catalog."""
        labels: set[str] = set()
        collections = (
            self.traits,
            self.preferences,
            self.aspirations,
            self.aspiration_tracks,
            self.aspiration_categories,
            self.careers,
            self.career_tracks,
            self.career_levels,
            self.milestones,
            self.relationship_bits,
        )
        for collection in collections:
            for item in collection.values():
                if item.source is not None:
                    labels.add(item.source.label)
        return sorted(labels)

    # ------------------------------------------------------------------
    # portable snapshots
    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        """Write this catalog to a pickle snapshot and return its path."""
        target = Path(path)
        try:
            if target.parent:
                target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError as exc:
            raise CatalogError(f"cannot write catalog to {target}: {exc}") from exc
        return target

    @classmethod
    def load(cls, path: str | Path) -> "Catalog":
        """Load a catalog written by :meth:`save`."""
        target = Path(path)
        try:
            with target.open("rb") as handle:
                value = pickle.load(handle)
        except OSError as exc:
            raise CatalogError(f"cannot read catalog from {target}: {exc}") from exc
        except Exception as exc:
            raise CatalogError(
                f"{target} is not a valid catalog snapshot: {exc}"
            ) from exc
        if not isinstance(value, cls):
            raise CatalogError(f"{target} does not contain a Catalog")
        return value

    def relationship_default(self, link: str) -> Optional[RelationshipDefault]:
        return self.relationship_defaults.get(link)

    def premade_relationship(
        self, sim_a: int, sim_b: int
    ) -> Optional[PremadeRelationship]:
        for relationship in self.premade_relationships:
            if (
                relationship.sim_a == sim_a
                and relationship.sim_b == sim_b
            ) or (
                relationship.sim_a == sim_b
                and relationship.sim_b == sim_a
            ):
                return relationship
        return None

    def is_family_trope(self, bit_id: int) -> bool:
        return bit_id in self.family_trope_ids

    def is_romance_trope(self, bit_id: int) -> bool:
        return bit_id in self.romance_trope_ids

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
