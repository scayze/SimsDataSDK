"""Extract pre-made Sims, households, and ancestors without a save file.

In The Sims 4 the concrete pre-made population is defined in two places:

* tuning — ``PremadeSimTemplate`` (name, referenced ``.siminfo`` resource,
  explicit traits/skills, primary aspiration, career level, dynasty and occult
  data), ``PremadeHouseholdTemplate`` (household members and their
  relationships) and ``TunablePremadeAncestor`` (ancestors used to build family
  trees);
* starter-save household resources (``0xB3C438F0``) — the older-pack pre-mades
  (BFF, Pancakes, Caliente, Roomies, Spencer-Kim-Lewis, ...) which have no
  tuning template at all.  These carry names, gender, age, traits, aspiration
  track, career, raw skill values and household funds.  They are located
  through the lot manifest (``0x729F6C4F``); see :mod:`sims4_sdk.catalog.worlds`.

The referenced ``.siminfo`` resource contains the traits that were baked into the
Sim, including the result of ``num_random`` trait assignment.  Step 2 reads that
trait list with :class:`sims4_sdk.siminfo.SimInfo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..core import DBPF, ResourceKey, TuningElement
from ..export import Serializable
from ..installation import Installation
from ..siminfo import SimInfo, SimInfoError
from .models import (
    Aspiration,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    GenderOptions,
    PremadeFamilyFixup,
    PremadeRelationship,
    Preference,
    SkillLevel,
    Trait,
    TuningSource,
)
from .relationships import FRIENDSHIP_TRACK_ID, ROMANCE_TRACK_ID
from .diagnostics import ExtractionIssue
from .values import TuningView
from .worlds import StarterMember, WorldData

__all__ = [
    "PremadeSim",
    "PremadeHousehold",
    "PremadeAncestor",
    "PremadeLot",
    "HouseholdMember",
    "HouseholdRelationship",
    "PremadeFamilyLink",
    "FamilyTreeNode",
    "FamilyTree",
    "PremadeBundle",
    "build_premades",
    "parse_resource_key",
]


def _exact_name(mapping: dict[str, object], key: str):
    item = mapping.get(key)
    if item is not None:
        return item
    needle = key.casefold()
    return next(
        (value for name, value in mapping.items() if name.casefold() == needle),
        None,
    )


def _source_matches(source: Optional[TuningSource], pack: Optional[str]) -> bool:
    if not pack:
        return True
    if source is None:
        return False
    needle = pack.casefold()
    return needle in (source.pack.casefold(), source.label.casefold())


@dataclass
class PremadeLot(Serializable):
    """A lot from the world/lot manifest (``0x729F6C4F``).

    ``household_id`` is the instance of the ``0xB3C438F0`` household resource
    that occupies the lot, when the lot ships with a pre-made household.
    """

    id: int
    lot_name: Optional[str] = None
    lot_description: Optional[str] = None
    household_name: Optional[str] = None
    household_description: Optional[str] = None
    household_id: Optional[int] = None
    lot_name_key: Optional[int] = None
    lot_description_key: Optional[int] = None
    source: Optional[TuningSource] = None

    @property
    def has_household(self) -> bool:
        return self.household_id is not None

    def __repr__(self) -> str:
        return f"PremadeLot({self.lot_name!r}, household={self.household_name!r})"


@dataclass
class HouseholdMember(Serializable):
    tag: str
    sim_template_id: int
    sim_name: Optional[str] = None
    full_name: Optional[str] = None


@dataclass
class HouseholdRelationship(Serializable):
    kind: str
    a_tag: str
    b_tag: str
    family_relationship: Optional[str] = None
    friendship: Optional[float] = None
    romance: Optional[float] = None
    friendship_min: Optional[float] = None
    friendship_max: Optional[float] = None
    romance_min: Optional[float] = None
    romance_max: Optional[float] = None
    bit_ids: list[int] = field(default_factory=list)


@dataclass
class PremadeFamilyLink(Serializable):
    """One typed kinship edge, preserving the tuning relation kind.

    ``MOTHER``/``FATHER``/``PARENT``/``SECRET_PARENT`` are direct parents;
    ``CHILD`` is a direct child; ``SIBLING`` is a sibling; other kinds
    (``MOTHERS_MOM``, ``FATHERS_FATHER``, ``GRANDPARENT``, ...) are
    extended family.  ``FIANCE``/``SPOUSE``/``STEADY`` are partners.

    ``name``/``sim_id`` are set when the relative resolves to a
    :class:`PremadeSim` or :class:`PremadeAncestor` (distinguished by
    ``target_kind``: ``"sim"``, ``"ancestor"``, or ``"unlinked"``);
    ``target_id`` always holds the raw relation target so dangling
    references outside the household are not silently dropped.
    """

    kind: str
    name: Optional[str] = None
    sim_id: Optional[int] = None
    target_id: Optional[int] = None
    target_kind: str = "sim"

    def __post_init__(self) -> None:
        if self.sim_id is None and self.target_kind == "sim":
            self.target_kind = "unlinked"

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        if "target_kind" not in state:
            self.target_kind = "unlinked" if self.sim_id is None else "sim"


@dataclass
class PremadeHousehold(Serializable):
    id: int
    name: str
    members: list[HouseholdMember] = field(default_factory=list)
    relationships: list[HouseholdRelationship] = field(default_factory=list)
    hidden: bool = False
    townie_street: Optional[str] = None
    funds: Optional[int] = None
    source: Optional[TuningSource] = None
    localized_name: Optional[str] = None
    description: Optional[str] = None
    lot_ids: list[int] = field(default_factory=list)

    def __setstate__(self, state: dict) -> None:
        # Portable snapshots created before lot links existed have no list field.
        self.__dict__.update(state)
        if "lot_ids" not in state:
            self.lot_ids = []

    @property
    def display_name(self) -> Optional[str]:
        """Localized manifest name, or a fallback inferred from the tuning name."""
        return self.localized_name or _household_display_name(self.name) or (
            self.name if not self.name.startswith(("premade", "HH_Template_", "hH_Template_")) else None
        )

    @property
    def lot_id(self) -> Optional[int]:
        """The lot manifest ID if exactly one lot references this household."""
        return self.lot_ids[0] if len(self.lot_ids) == 1 else None

    @property
    def member_ids(self) -> list[int]:
        return [member.sim_template_id for member in self.members]

    def __repr__(self) -> str:
        return f"PremadeHousehold({self.name!r}, members={len(self.members)})"


@dataclass
class PremadeAncestor(Serializable):
    id: int
    name: str
    full_name: str
    gender: Optional[str] = None
    death_trait_id: Optional[int] = None
    thumbnail: Optional[str] = None
    spouse_id: Optional[int] = None
    spouse_name: Optional[str] = None
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    siblings: list[str] = field(default_factory=list)
    extended_family: list[str] = field(default_factory=list)
    parent_links: list[PremadeFamilyLink] = field(default_factory=list)
    child_links: list[PremadeFamilyLink] = field(default_factory=list)
    sibling_links: list[PremadeFamilyLink] = field(default_factory=list)
    extended_family_links: list[PremadeFamilyLink] = field(default_factory=list)
    source: Optional[TuningSource] = None

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        for missing, default in (
            ("spouse_id", None),
            ("spouse_name", None),
            ("parents", []),
            ("children", []),
            ("siblings", []),
            ("extended_family", []),
            ("parent_links", []),
            ("child_links", []),
            ("sibling_links", []),
            ("extended_family_links", []),
        ):
            if missing not in state:
                setattr(
                    self,
                    missing,
                    list(default) if isinstance(default, list) else default,
                )

    def __repr__(self) -> str:
        return f"PremadeAncestor({self.full_name!r})"


@dataclass
class PremadeSim(Serializable):
    id: int
    name: str
    first_name: str
    last_name: str
    siminfo_key: Optional[ResourceKey] = None
    explicit_trait_ids: list[int] = field(default_factory=list)
    siminfo_trait_ids: list[int] = field(default_factory=list)
    traits: list[Trait] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    unknown_trait_ids: list[int] = field(default_factory=list)
    random_trait_count: Optional[int] = None
    skills: list[SkillLevel] = field(default_factory=list)
    aspiration_id: Optional[int] = None
    aspiration: Optional[Aspiration] = None
    career_level_id: Optional[int] = None
    career_level: Optional[CareerLevel] = None
    dynasty: dict = field(default_factory=dict)
    occult_type: Optional[str] = None
    pregnancy: dict = field(default_factory=dict)
    pronouns: Optional[str] = None
    household_id: Optional[int] = None
    household_name: Optional[str] = None
    spouse_id: Optional[int] = None
    spouse_name: Optional[str] = None
    fiance_id: Optional[int] = None
    fiance_name: Optional[str] = None
    steady_ids: list[int] = field(default_factory=list)
    steady_names: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    siblings: list[str] = field(default_factory=list)
    extended_family: list[str] = field(default_factory=list)
    #: Typed kinship preserving the tuning ``family_relationship`` kind.
    #: ``parents``/``extended_family`` stay as plain names for compatibility.
    parent_links: list[PremadeFamilyLink] = field(default_factory=list)
    child_links: list[PremadeFamilyLink] = field(default_factory=list)
    sibling_links: list[PremadeFamilyLink] = field(default_factory=list)
    extended_family_links: list[PremadeFamilyLink] = field(default_factory=list)
    #: Relation targets with no matching Sim in the static data
    #: (e.g. starter ``gameplay.14`` parents outside the household).
    unlinked_relations: list[PremadeFamilyLink] = field(default_factory=list)
    aspiration_track_id: Optional[int] = None
    aspiration_track: Optional[AspirationTrack] = None
    career_id: Optional[int] = None
    career: Optional[Career] = None
    career_track_id: Optional[int] = None
    career_track: Optional[CareerTrack] = None
    #: Starting career level from a starter-save resource (0-based index and
    #: 1-based in-game display level).
    career_track_level: Optional[int] = None
    career_display_level: Optional[int] = None
    #: Raw hints from starter-save household resources (``0xB3C438F0``).
    gender_hint: Optional[str] = None
    age_hint: Optional[str] = None
    body_blend: Optional[str] = None
    source: Optional[TuningSource] = None

    @property
    def full_name(self) -> str:
        parts = [part for part in (self.first_name, self.last_name) if part]
        return " ".join(parts) or self.name

    @property
    def trait_names(self) -> list[str]:
        return [trait.name for trait in self.traits]

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
        """Traits that are not purely internal (gender, walk style, species...)."""
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
    def preference_names(self) -> list[str]:
        return [preference.name for preference in self.preferences]

    @property
    def likes(self) -> list[Preference]:
        return [preference for preference in self.preferences if preference.is_like]

    @property
    def dislikes(self) -> list[Preference]:
        return [preference for preference in self.preferences if preference.is_dislike]

    @property
    def species(self) -> Optional[str]:
        for trait in self.traits:
            if trait.name.startswith("trait_Species_"):
                return trait.name[len("trait_Species_") :]
        return None

    @property
    def occult(self) -> Optional[str]:
        if self.occult_type:
            return self.occult_type
        for trait in self.traits:
            if trait.name.startswith("trait_Occult_"):
                return trait.name[len("trait_Occult_") :]
        return None

    @property
    def gender(self) -> Optional[str]:
        if self.gender_hint:
            return self.gender_hint
        for trait in self.traits:
            if trait.name in ("trait_GenderMale", "trait_GenderFemale"):
                return trait.name[len("trait_Gender") :].upper()
        return None

    @property
    def age(self) -> Optional[str]:
        mapping = {
            "baby": "BABY",
            "infant": "INFANT",
            "toddler": "TODDLER",
            "child": "CHILD",
            "teen": "TEEN",
            "youngadult": "YOUNGADULT",
            "adult": "ADULT",
            "elder": "ELDER",
        }
        for trait in self.traits:
            if trait.name.startswith("trait_"):
                key = trait.name[len("trait_") :].casefold()
                if key in mapping:
                    return mapping[key]
        return self.age_hint

    def __setstate__(self, state: dict) -> None:
        # Snapshots predating fiance/typed-kinship fields lack them.
        self.__dict__.update(state)
        for missing, default in (
            ("fiance_id", None),
            ("fiance_name", None),
            ("steady_ids", []),
            ("steady_names", []),
            ("parent_links", []),
            ("child_links", []),
            ("sibling_links", []),
            ("extended_family_links", []),
            ("unlinked_relations", []),
        ):
            if missing not in state:
                setattr(
                    self,
                    missing,
                    list(default) if isinstance(default, list) else default,
                )

    def __repr__(self) -> str:
        return f"PremadeSim({self.full_name!r}, traits={len(self.traits)})"


@dataclass
class FamilyTreeNode(Serializable):
    """One Sim or ancestor node inside a :class:`FamilyTree`."""

    id: int
    name: str
    full_name: str
    kind: str = "sim"
    gender: Optional[str] = None
    age: Optional[str] = None
    is_ghost_or_ancestor: bool = False
    household_id: Optional[int] = None
    household_name: Optional[str] = None
    thumbnail: Optional[str] = None
    death_trait_id: Optional[int] = None
    spouse_id: Optional[int] = None
    spouse_name: Optional[str] = None
    fiance_id: Optional[int] = None
    fiance_name: Optional[str] = None
    steady_ids: list[int] = field(default_factory=list)
    parent_ids: list[int] = field(default_factory=list)
    secret_parent_ids: list[int] = field(default_factory=list)
    child_ids: list[int] = field(default_factory=list)
    sibling_ids: list[int] = field(default_factory=list)
    parent_links: list[PremadeFamilyLink] = field(default_factory=list)
    child_links: list[PremadeFamilyLink] = field(default_factory=list)
    sibling_links: list[PremadeFamilyLink] = field(default_factory=list)
    extended_family_links: list[PremadeFamilyLink] = field(default_factory=list)
    unlinked_relations: list[PremadeFamilyLink] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"FamilyTreeNode({self.full_name!r}, kind={self.kind!r}, parents={len(self.parent_ids)}, children={len(self.child_ids)})"


@dataclass
class FamilyTree(Serializable):
    """Multi-generational genealogy graph around a pre-made Sim or ancestor."""

    root_id: int
    nodes: dict[int, FamilyTreeNode] = field(default_factory=dict)
    unlinked_relations: list[PremadeFamilyLink] = field(default_factory=list)

    @property
    def root(self) -> Optional[FamilyTreeNode]:
        return self.nodes.get(self.root_id)

    def node(self, sim_id: int) -> Optional[FamilyTreeNode]:
        return self.nodes.get(sim_id)

    def ancestors_of(self, sim_id: Optional[int] = None) -> list[FamilyTreeNode]:
        """Return all transitive ancestors of ``sim_id`` (defaults to ``root_id``)."""
        start = self.root_id if sim_id is None else sim_id
        seen: set[int] = set()
        result: list[FamilyTreeNode] = []
        queue = list(
            self.nodes[start].parent_ids + self.nodes[start].secret_parent_ids
            if start in self.nodes
            else []
        )
        while queue:
            current_id = queue.pop(0)
            if current_id in seen:
                continue
            seen.add(current_id)
            node = self.nodes.get(current_id)
            if node is not None:
                result.append(node)
                for parent_id in [*node.parent_ids, *node.secret_parent_ids]:
                    if parent_id not in seen:
                        queue.append(parent_id)
        return result

    def descendants_of(self, sim_id: Optional[int] = None) -> list[FamilyTreeNode]:
        """Return all transitive descendants of ``sim_id`` (defaults to ``root_id``)."""
        start = self.root_id if sim_id is None else sim_id
        seen: set[int] = set()
        result: list[FamilyTreeNode] = []
        queue = list(self.nodes[start].child_ids if start in self.nodes else [])
        while queue:
            current_id = queue.pop(0)
            if current_id in seen:
                continue
            seen.add(current_id)
            node = self.nodes.get(current_id)
            if node is not None:
                result.append(node)
                for child_id in node.child_ids:
                    if child_id not in seen:
                        queue.append(child_id)
        return result

    def __len__(self) -> int:
        return len(self.nodes)

    def __repr__(self) -> str:
        root_name = self.root.full_name if self.root else hex(self.root_id)
        return f"FamilyTree({root_name!r}, nodes={len(self.nodes)})"


@dataclass
class PremadeBundle(Serializable):
    sims: list[PremadeSim] = field(default_factory=list)
    households: list[PremadeHousehold] = field(default_factory=list)
    ancestors: list[PremadeAncestor] = field(default_factory=list)
    lots: list[PremadeLot] = field(default_factory=list)
    premade_relationships: list[PremadeRelationship] = field(default_factory=list)
    family_fixups: list[PremadeFamilyFixup] = field(default_factory=list)
    sims_by_name: dict[str, PremadeSim] = field(default_factory=dict, repr=False)
    ancestors_by_name: dict[str, PremadeAncestor] = field(
        default_factory=dict, repr=False
    )
    households_by_name: dict[str, PremadeHousehold] = field(
        default_factory=dict, repr=False
    )
    lots_by_name: dict[str, PremadeLot] = field(default_factory=dict, repr=False)

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        if "family_fixups" not in state:
            self.family_fixups = []
        if "ancestors_by_name" not in state:
            self.ancestors_by_name = {}
            for ancestor in self.ancestors:
                self.ancestors_by_name.setdefault(ancestor.name, ancestor)
                self.ancestors_by_name.setdefault(ancestor.full_name, ancestor)

    def sim(self, key: str | int) -> Optional[PremadeSim]:
        """Look up a Sim by ID, exact name, or unambiguous name fragment."""
        if isinstance(key, int):
            return next((sim for sim in self.sims if sim.id == key), None)
        exact = _exact_name(self.sims_by_name, key)
        if exact is not None:
            return exact
        found = self.find_sims(key)
        return found[0] if found else None

    def ancestor(self, key: str | int) -> Optional[PremadeAncestor]:
        """Look up an ancestor by ID, exact name, or name fragment."""
        if isinstance(key, int):
            return next((anc for anc in self.ancestors if anc.id == key), None)
        exact = _exact_name(self.ancestors_by_name, key)
        if exact is not None:
            return exact
        found = self.find_ancestors(key)
        return found[0] if found else None

    def household(self, key: str | int) -> Optional[PremadeHousehold]:
        """Look up a household by ID, exact name, or name fragment."""
        if isinstance(key, int):
            return next((hh for hh in self.households if hh.id == key), None)
        exact = _exact_name(self.households_by_name, key)
        if exact is not None:
            return exact
        needle = key.casefold()
        return next(
            (hh for hh in self.households if needle in hh.name.casefold()
             or needle in (hh.display_name or "").casefold()), None
        )

    def lot(self, key: str | int) -> Optional[PremadeLot]:
        """Look up a lot by ID, exact name, or name fragment."""
        if isinstance(key, int):
            return next((lot for lot in self.lots if lot.id == key), None)
        exact = _exact_name(self.lots_by_name, key)
        if exact is not None:
            return exact
        needle = key.casefold()
        return next(
            (lot for lot in self.lots if needle in (lot.lot_name or "").casefold()),
            None,
        )

    def find_sims(
        self,
        query: str = "",
        *,
        pack: Optional[str] = None,
        household: str | int | None = None,
        age: Optional[str] = None,
        occult: Optional[str] = None,
    ) -> list[PremadeSim]:
        """Filter pre-made Sims by name, pack, household, age, or occult."""
        needle = query.casefold()
        results: list[PremadeSim] = []
        for sim in self.sims:
            if needle and needle not in sim.full_name.casefold() and needle not in sim.name.casefold():
                continue
            if not _source_matches(sim.source, pack):
                continue
            if household is not None:
                if isinstance(household, int):
                    if sim.household_id != household:
                        continue
                elif (sim.household_name or "").casefold() != household.casefold():
                    continue
            if age and (sim.age or "").casefold() != age.casefold():
                continue
            if occult and (sim.occult or "").casefold() != occult.casefold():
                continue
            results.append(sim)
        return results

    def find_households(
        self,
        query: str = "",
        *,
        pack: Optional[str] = None,
    ) -> list[PremadeHousehold]:
        needle = query.casefold()
        return [
            household
            for household in self.households
            if (not needle or needle in household.name.casefold()
                or needle in (household.display_name or "").casefold())
            and _source_matches(household.source, pack)
        ]

    def find_lots(
        self,
        query: str = "",
        *,
        pack: Optional[str] = None,
        occupied_only: bool = False,
    ) -> list[PremadeLot]:
        needle = query.casefold()
        return [
            lot
            for lot in self.lots
            if (
                not needle
                or needle in (lot.lot_name or "").casefold()
                or needle in (lot.household_name or "").casefold()
            )
            and _source_matches(lot.source, pack)
            and not (occupied_only and not lot.has_household)
        ]

    def relationship(
        self, sim_a: int, sim_b: int
    ) -> Optional[PremadeRelationship]:
        for relationship in self.premade_relationships:
            if {relationship.sim_a, relationship.sim_b} == {sim_a, sim_b}:
                return relationship
        return None

    def relationships_for(self, sim: int | PremadeSim) -> list[PremadeRelationship]:
        sim_id = sim.id if isinstance(sim, PremadeSim) else sim
        return [
            relationship
            for relationship in self.premade_relationships
            if sim_id in (relationship.sim_a, relationship.sim_b)
        ]

    def find_ancestors(
        self,
        query: str = "",
        *,
        pack: Optional[str] = None,
    ) -> list[PremadeAncestor]:
        """Filter pre-made ancestors by name or pack."""
        needle = query.casefold()
        return [
            ancestor
            for ancestor in self.ancestors
            if (
                not needle
                or needle in ancestor.full_name.casefold()
                or needle in ancestor.name.casefold()
            )
            and _source_matches(ancestor.source, pack)
        ]

    def family_tree(
        self,
        key: str | int | PremadeSim | PremadeAncestor,
    ) -> Optional[FamilyTree]:
        """Build the connected multi-generational family tree around ``key``."""
        if isinstance(key, (PremadeSim, PremadeAncestor)):
            target = key
        else:
            target = self.sim(key) or self.ancestor(key)
        if target is None:
            return None
        return _build_family_tree(self, target.id)

    def __len__(self) -> int:
        return len(self.sims)


# ----------------------------------------------------------------------
# extraction
# ----------------------------------------------------------------------
def build_premades(
    installation: Installation,
    catalog: Catalog,
    entries: dict[int, TuningElement],
    sources: dict[int, TuningSource],
    *,
    world: Optional[WorldData] = None,
    siminfo_index: Optional[dict[int, tuple]] = None,
) -> PremadeBundle:
    sims: dict[int, PremadeSim] = {}
    households: dict[int, PremadeHousehold] = {}
    ancestors: dict[int, PremadeAncestor] = {}
    # The package scan already indexed every SimInfo resource; re-opening all
    # package indexes here would cost another full DBPF parse pass.
    if siminfo_index is None:
        siminfo_index = installation.siminfo_index()

    for instance_id, entry in entries.items():
        cls = entry.cls
        try:
            if cls == "PremadeSimTemplate":
                view = TuningView(entry, catalog.strings)
                sims[instance_id] = _build_sim(
                    entry, view, sources.get(instance_id), siminfo_index, catalog
                )
            elif cls == "PremadeHouseholdTemplate":
                households[instance_id] = _build_household(
                    entry, TuningView(entry, catalog.strings), sources.get(instance_id)
                )
            elif cls == "TunablePremadeAncestor":
                ancestors[instance_id] = _build_ancestor(
                    entry, TuningView(entry, catalog.strings), sources.get(instance_id)
                )
        except Exception as exc:
            catalog.errors.append(f"{entry.name} ({cls}): {exc}")
            source = sources.get(instance_id)
            catalog.diagnostics.append(ExtractionIssue.from_exception(
                "premade_model", exc, package_path=source.path if source else None,
                resource_key=source.resource_key if source else None, tuning_id=instance_id,
            ))

    for household in households.values():
        for member in household.members:
            sim = sims.get(member.sim_template_id)
            if sim is not None:
                member.sim_name = sim.name
                member.full_name = sim.full_name
                sim.household_id = household.id
                sim.household_name = household.name

    if world is not None:
        aliases, household_id_aliases = _merge_world(catalog, sims, households, world)
    else:
        aliases, household_id_aliases = {}, {}

    _link_household_relationships(households.values(), sims, catalog)
    _link_cross_household_and_ancestors(sims, ancestors, catalog)
    _apply_relationship_defaults(households.values(), catalog, sims)

    lots = _build_lots(catalog, world, household_id_aliases)
    _link_lots(households, lots)
    bundle = PremadeBundle(
        sims=sorted(sims.values(), key=lambda sim: sim.full_name.casefold()),
        households=sorted(households.values(), key=lambda hh: hh.name.casefold()),
        ancestors=sorted(ancestors.values(), key=lambda anc: anc.full_name.casefold()),
        lots=lots,
        premade_relationships=list(catalog.premade_relationships),
        family_fixups=list(catalog.family_fixups),
    )
    for relationship in bundle.premade_relationships:
        a = sims.get(relationship.sim_a) or ancestors.get(relationship.sim_a)
        b = sims.get(relationship.sim_b) or ancestors.get(relationship.sim_b)
        if a is not None:
            relationship.sim_a_name = a.full_name
        if b is not None:
            relationship.sim_b_name = b.full_name
    for fixup in bundle.family_fixups:
        a = sims.get(fixup.sim_a) or ancestors.get(fixup.sim_a)
        b = sims.get(fixup.sim_b) or ancestors.get(fixup.sim_b)
        if a is not None:
            fixup.sim_a_name = a.full_name
        if b is not None:
            fixup.sim_b_name = b.full_name
    for sim in bundle.sims:
        bundle.sims_by_name.setdefault(sim.name, sim)
        bundle.sims_by_name.setdefault(sim.full_name, sim)
    for ancestor in bundle.ancestors:
        bundle.ancestors_by_name.setdefault(ancestor.name, ancestor)
        bundle.ancestors_by_name.setdefault(ancestor.full_name, ancestor)
    for household in bundle.households:
        bundle.households_by_name.setdefault(household.name, household)
        inferred_name = _household_display_name(household.name)
        if inferred_name:
            bundle.households_by_name.setdefault(inferred_name, household)
        display_name = household.display_name
        if display_name:
            bundle.households_by_name.setdefault(display_name, household)
    for alias, household in aliases.items():
        bundle.households_by_name.setdefault(alias, household)
    for lot in bundle.lots:
        if lot.lot_name:
            bundle.lots_by_name.setdefault(lot.lot_name, lot)
    return bundle


def _link_lots(households: dict[int, PremadeHousehold], lots: list[PremadeLot]) -> None:
    """Attach manifest links without choosing between conflicting localized values."""
    grouped: dict[int, list[PremadeLot]] = {}
    for lot in lots:
        if lot.household_id in households:
            grouped.setdefault(lot.household_id, []).append(lot)
    for household_id, household_lots in grouped.items():
        household = households[household_id]
        household.lot_ids = sorted({lot.id for lot in household_lots})
        names = {lot.household_name for lot in household_lots if lot.household_name}
        descriptions = {lot.household_description for lot in household_lots if lot.household_description}
        household.localized_name = next(iter(names)) if len(names) == 1 else None
        household.description = next(iter(descriptions)) if len(descriptions) == 1 else None


def _merge_world(
    catalog: Catalog,
    sims: dict[int, PremadeSim],
    households: dict[int, PremadeHousehold],
    world: WorldData,
) -> tuple[dict[str, PremadeHousehold], dict[int, int]]:
    """Merge ``0xB3C438F0`` households into the tuning-derived population.

    A legacy household is skipped when tuning already defines every one of its
    members (that is the case for Goth, Landgraabs and Zest, which have both a
    ``PremadeHouseholdTemplate`` and a starter-save resource).  Partially
    covered households link the existing tuning Sims and add the rest.

    Returns the household-name aliases and a map from legacy resource instance
    IDs to the household ID they were merged into (used to resolve lot links).
    """
    aliases: dict[str, PremadeHousehold] = {}
    household_id_aliases: dict[int, int] = {}
    by_name: dict[str, PremadeSim] = {}
    for sim in sims.values():
        if sim.full_name:
            by_name.setdefault(sim.full_name.casefold(), sim)

    tuning_by_members = {
        frozenset(member.full_name.casefold() for member in household.members if member.full_name): household
        for household in households.values()
        if household.members
    }
    households_by_name = {
        household.name.casefold(): household for household in households.values()
    }
    taken_names = {household.name.casefold() for household in households.values()}

    for record in sorted(
        world.households.values(), key=lambda item: (item.name.casefold(), item.instance)
    ):
        if not record.members:
            continue

        # Some packs (for example EP10) store the household resource under the
        # same name as the tuning template but with unnamed members.  In that
        # case the members line up by position; just attach the hints.
        match = households_by_name.get(record.name.casefold()) if record.name else None
        if (
            match is not None
            and match.members
            and len(match.members) == len(record.members)
        ):
            for household_member, member in zip(match.members, record.members):
                sim = sims.get(household_member.sim_template_id)
                if sim is not None:
                    _apply_hints(catalog, sim, member)
            if match.funds is None and record.funds is not None:
                match.funds = record.funds
            sim_by_tag = {
                member.tag: sims[member.sim_template_id]
                for member in match.members
                if member.sim_template_id in sims
            }
            _link_starter_family(None, record.members, sim_by_tag)
            aliases.setdefault(record.name, match)
            household_id_aliases[record.instance] = match.id
            continue

        covered = sum(
            1 for member in record.members if member.full_name.casefold() in by_name
        )
        if covered == len(record.members):
            # Tuning already defines every member.  Attach the resource's
            # household funds and any per-Sim hints that tuning leaves blank.
            key = frozenset(
                member.full_name.casefold() for member in record.members if member.full_name
            )
            match = tuning_by_members.get(key)
            if match is not None:
                if match.funds is None and record.funds is not None:
                    match.funds = record.funds
                if record.name:
                    aliases.setdefault(record.name, match)
                household_id_aliases[record.instance] = match.id
            for member in record.members:
                existing = by_name.get(member.full_name.casefold())
                if existing is not None:
                    _apply_hints(catalog, existing, member)
            sim_by_tag = {
                f"household_member_{index}": by_name[member.full_name.casefold()]
                for index, member in enumerate(record.members, start=1)
                if member.full_name.casefold() in by_name
            }
            _link_starter_family(None, record.members, sim_by_tag)
            continue
        if record.name and record.name.casefold() in taken_names:
            continue

        household = PremadeHousehold(
            id=record.instance,
            name=record.name or f"household_{record.instance:016X}",
            funds=record.funds,
            source=record.source,
        )
        taken_names.add(household.name.casefold())

        sim_by_tag: dict[str, PremadeSim] = {}
        for index, member in enumerate(record.members, start=1):
            tag = f"household_member_{index}"
            existing = by_name.get(member.full_name.casefold())
            if existing is None:
                existing = _starter_sim(catalog, household, member, index)
                sims[existing.id] = existing
                by_name[member.full_name.casefold()] = existing
            sim_by_tag[tag] = existing
            household.members.append(
                HouseholdMember(
                    tag=tag,
                    sim_template_id=existing.id,
                    sim_name=existing.name,
                    full_name=existing.full_name,
                )
            )

        _link_starter_family(household, record.members, sim_by_tag)
        households[household.id] = household

    return aliases, household_id_aliases


def _link_starter_family(
    household: Optional[PremadeHousehold],
    members: list[StarterMember],
    sim_by_tag: dict[str, PremadeSim],
) -> None:
    """Attach spouse/fiance/parent/child/sibling links from ``0xB3C438F0``.

    The resource stores the spouse in member field 15, the fiance in field
    68, steadies in field 72, and ancestor relations in ``gameplay.14`` as
    ``(relation_type, target_sim_id)`` pairs.  ``None`` for ``household``
    means the tuning household already owns the relationship list
    (Goth/Landgraabs/Zest); only the Sim-level fields are filled then.
    Relations whose target has no member in this record are kept on
    :attr:`PremadeSim.unlinked_relations` instead of being dropped.
    """
    tag_by_id = {
        member.sim_id: f"household_member_{index}"
        for index, member in enumerate(members, start=1)
        if member.sim_id
    }

    spouse_pairs: set[frozenset[str]] = set()
    for index, member in enumerate(members, start=1):
        tag = f"household_member_{index}"
        if not member.spouse_id:
            continue
        spouse_tag = tag_by_id.get(member.spouse_id)
        if not spouse_tag:
            continue
        pair = frozenset((tag, spouse_tag))
        if pair in spouse_pairs:
            continue
        spouse_pairs.add(pair)
        if household is not None:
            household.relationships.append(
                HouseholdRelationship(kind="spouse", a_tag=tag, b_tag=spouse_tag)
            )

    fiance_pairs: set[frozenset[str]] = set()
    for index, member in enumerate(members, start=1):
        tag = f"household_member_{index}"
        if not member.fiance_id:
            continue
        fiance_tag = tag_by_id.get(member.fiance_id)
        if not fiance_tag:
            continue
        pair = frozenset((tag, fiance_tag))
        if pair in fiance_pairs:
            continue
        fiance_pairs.add(pair)
        if household is not None:
            household.relationships.append(
                HouseholdRelationship(kind="fiance", a_tag=tag, b_tag=fiance_tag)
            )

    steady_pairs: set[frozenset[str]] = set()
    for index, member in enumerate(members, start=1):
        tag = f"household_member_{index}"
        for steady_id in member.steady_ids or ():
            steady_tag = tag_by_id.get(steady_id)
            if not steady_tag or steady_tag == tag:
                continue
            pair = frozenset((tag, steady_tag))
            if pair in steady_pairs:
                continue
            steady_pairs.add(pair)
            if household is not None:
                household.relationships.append(
                    HouseholdRelationship(kind="steady", a_tag=tag, b_tag=steady_tag)
                )

    parent_links: list[tuple[str, str, str, Optional[int]]] = []
    children_by_parent_target: dict[int, list[str]] = {}
    for index, member in enumerate(members, start=1):
        child_tag = f"household_member_{index}"
        for relation in member.relations:
            if relation.kind in ("MOTHER", "FATHER", "PARENT") and relation.target_id:
                children_by_parent_target.setdefault(relation.target_id, []).append(
                    child_tag
                )
            parent_tag = tag_by_id.get(relation.target_id)
            if not parent_tag:
                child = sim_by_tag.get(child_tag)
                if child is not None:
                    _append_link_unique(
                        child.unlinked_relations,
                        PremadeFamilyLink(
                            kind=relation.kind,
                            name=None,
                            sim_id=None,
                            target_id=relation.target_id,
                            target_kind="unlinked",
                        ),
                    )
                continue
            parent_links.append(
                (parent_tag, child_tag, relation.kind, relation.target_id)
            )
            if household is not None:
                household.relationships.append(
                    HouseholdRelationship(
                        kind="family",
                        a_tag=parent_tag,
                        b_tag=child_tag,
                        family_relationship=relation.kind,
                    )
                )

    for parent_tag, child_tag, kind, target_id in parent_links:
        parent = sim_by_tag.get(parent_tag)
        child = sim_by_tag.get(child_tag)
        if parent is None or child is None:
            continue
        if kind in ("MOTHER", "FATHER", "PARENT"):
            _link_parent_child(parent, child, kind=kind, target_id=target_id)
        else:
            _append_unique(child.extended_family, parent.full_name)
            _append_link_unique(
                child.extended_family_links,
                PremadeFamilyLink(
                    kind=kind,
                    name=parent.full_name,
                    sim_id=parent.id,
                    target_id=target_id,
                ),
            )

    for relationship in spouse_pairs:
        a_tag, b_tag = tuple(relationship)
        a = sim_by_tag.get(a_tag)
        b = sim_by_tag.get(b_tag)
        if a is None or b is None:
            continue
        a.spouse_id = b.id
        a.spouse_name = b.full_name
        b.spouse_id = a.id
        b.spouse_name = a.full_name

    for relationship in fiance_pairs:
        a_tag, b_tag = tuple(relationship)
        a = sim_by_tag.get(a_tag)
        b = sim_by_tag.get(b_tag)
        if a is None or b is None:
            continue
        if a.fiance_id is None:
            a.fiance_id = b.id
            a.fiance_name = b.full_name
        if b.fiance_id is None:
            b.fiance_id = a.id
            b.fiance_name = a.full_name

    for relationship in steady_pairs:
        a_tag, b_tag = tuple(relationship)
        a = sim_by_tag.get(a_tag)
        b = sim_by_tag.get(b_tag)
        if a is None or b is None:
            continue
        if b.id not in (a.steady_ids or []):
            a.steady_ids.append(b.id)
            _append_unique(a.steady_names, b.full_name)
        if a.id not in (b.steady_ids or []):
            b.steady_ids.append(a.id)
            _append_unique(b.steady_names, a.full_name)

    children_by_parent: dict[str | int, list[str]] = {}
    for parent_tag, child_tag, kind, _target_id in parent_links:
        if kind in ("MOTHER", "FATHER", "PARENT"):
            children_by_parent.setdefault(parent_tag, []).append(child_tag)
    for target_id, child_tags in children_by_parent_target.items():
        if len(child_tags) > 1:
            children_by_parent.setdefault(target_id, []).extend(child_tags)

    sibling_pairs_added: set[frozenset[str]] = set()
    for parent_key, child_tags in children_by_parent.items():
        for child_tag in child_tags:
            sim = sim_by_tag.get(child_tag)
            if sim is None:
                continue
            for sibling_tag in child_tags:
                if sibling_tag == child_tag:
                    continue
                sibling = sim_by_tag.get(sibling_tag)
                if sibling is not None:
                    _link_siblings(sim, sibling)
                    if (
                        household is not None
                        and isinstance(parent_key, int)
                        and parent_key not in tag_by_id
                    ):
                        pair = frozenset((child_tag, sibling_tag))
                        if pair not in sibling_pairs_added:
                            sibling_pairs_added.add(pair)
                            household.relationships.append(
                                HouseholdRelationship(
                                    kind="family",
                                    a_tag=child_tag,
                                    b_tag=sibling_tag,
                                    family_relationship="SIBLING",
                                )
                            )


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


_PARENT_KINDS = ("MOTHER", "FATHER", "PARENT", "SECRET_PARENT")


def _append_link_unique(
    values: list[PremadeFamilyLink], link: PremadeFamilyLink
) -> None:
    # Resolved edges can arrive twice (starter ``0xB3C438F0`` + tuning
    # template + fixups) with different raw ``target_id``s or generic ``PARENT``
    # vs specific ``MOTHER``/``FATHER`` kinds for the same Sim.
    if link.sim_id is not None:
        for existing in values:
            if existing.sim_id != link.sim_id:
                continue
            if existing.kind == link.kind:
                return
            if (
                existing.kind in ("MOTHER", "FATHER", "PARENT")
                and link.kind in ("MOTHER", "FATHER", "PARENT")
            ):
                if existing.kind == "PARENT" and link.kind in ("MOTHER", "FATHER"):
                    existing.kind = link.kind
                return
    else:
        key = (link.kind, link.target_id)
        for existing in values:
            if (existing.kind, existing.target_id) == key and existing.sim_id is None:
                return
    values.append(link)


def _node_target_kind(node: PremadeSim | PremadeAncestor) -> str:
    return "ancestor" if isinstance(node, PremadeAncestor) else "sim"


def _link_parent_child(
    parent: PremadeSim | PremadeAncestor,
    child: PremadeSim | PremadeAncestor,
    *,
    kind: str = "PARENT",
    target_id: Optional[int] = None,
) -> None:
    if parent.id == child.id:
        return
    _append_unique(child.parents, parent.full_name)
    _append_unique(parent.children, child.full_name)
    _append_link_unique(
        child.parent_links,
        PremadeFamilyLink(
            kind=kind,
            name=parent.full_name,
            sim_id=parent.id,
            target_id=target_id if target_id is not None else parent.id,
            target_kind=_node_target_kind(parent),
        ),
    )
    _append_link_unique(
        parent.child_links,
        PremadeFamilyLink(
            kind="CHILD",
            name=child.full_name,
            sim_id=child.id,
            target_id=child.id,
            target_kind=_node_target_kind(child),
        ),
    )


def _link_siblings(
    a: PremadeSim | PremadeAncestor,
    b: PremadeSim | PremadeAncestor,
) -> None:
    if a.id == b.id:
        return
    _append_unique(a.siblings, b.full_name)
    _append_unique(b.siblings, a.full_name)
    _append_link_unique(
        a.sibling_links,
        PremadeFamilyLink(
            kind="SIBLING",
            name=b.full_name,
            sim_id=b.id,
            target_id=b.id,
            target_kind=_node_target_kind(b),
        ),
    )
    _append_link_unique(
        b.sibling_links,
        PremadeFamilyLink(
            kind="SIBLING",
            name=a.full_name,
            sim_id=a.id,
            target_id=a.id,
            target_kind=_node_target_kind(a),
        ),
    )


def _link_extended(
    actor: PremadeSim | PremadeAncestor,
    relative: PremadeSim | PremadeAncestor,
    kind: str,
) -> None:
    if actor.id == relative.id:
        return
    _append_unique(actor.extended_family, relative.full_name)
    _append_link_unique(
        actor.extended_family_links,
        PremadeFamilyLink(
            kind=kind,
            name=relative.full_name,
            sim_id=relative.id,
            target_id=relative.id,
            target_kind=_node_target_kind(relative),
        ),
    )


def _link_household_relationships(
    households,
    sims: dict[int, PremadeSim],
    catalog: Optional[Catalog] = None,
) -> None:
    """Fill Sim-level spouse/fiance/parent/child/sibling fields from links.

    Works for tuning households (``PremadeHouseholdTemplate``) and for starter
    households whose links were decoded from ``0xB3C438F0``.  In both formats
    ``a_tag`` is the parent/spouse and ``b_tag`` is the child/spouse.
    """
    marriage_bit = catalog.marriage_bit_id if catalog is not None else 15822
    engagement_bit = catalog.engagement_bit_id if catalog is not None else 15816
    steady_bit = catalog.steady_bit_id if catalog is not None else 15825

    for household in households:
        tag_to_sim: dict[str, PremadeSim] = {}
        for member in household.members:
            sim = sims.get(member.sim_template_id)
            if sim is not None:
                tag_to_sim[member.tag] = sim

        for relationship in household.relationships:
            a = tag_to_sim.get(relationship.a_tag)
            b = tag_to_sim.get(relationship.b_tag)
            if a is None or b is None:
                continue
            if relationship.kind == "spouse" or (
                marriage_bit and marriage_bit in relationship.bit_ids
            ):
                a.spouse_id = b.id
                a.spouse_name = b.full_name
                b.spouse_id = a.id
                b.spouse_name = a.full_name
            elif relationship.kind == "fiance" or (
                engagement_bit and engagement_bit in relationship.bit_ids
            ):
                if a.fiance_id is None:
                    a.fiance_id = b.id
                    a.fiance_name = b.full_name
                if b.fiance_id is None:
                    b.fiance_id = a.id
                    b.fiance_name = a.full_name
            elif relationship.kind == "steady" or (
                steady_bit and steady_bit in relationship.bit_ids
            ):
                if b.id not in (a.steady_ids or []):
                    a.steady_ids.append(b.id)
                    _append_unique(a.steady_names, b.full_name)
                if a.id not in (b.steady_ids or []):
                    b.steady_ids.append(a.id)
                    _append_unique(b.steady_names, a.full_name)

            if 8802 in relationship.bit_ids:
                _link_siblings(a, b)
            if 8829 in relationship.bit_ids:
                _link_extended(b, a, "PARENTS_SIBLING")
                _link_extended(a, b, "SIBLINGS_CHILDREN")
            if 8826 in relationship.bit_ids:
                _link_extended(a, b, "COUSIN")
                _link_extended(b, a, "COUSIN")

        children_by_parent: dict[str, list[str]] = {}
        for relationship in household.relationships:
            if relationship.kind != "family":
                continue
            parent = tag_to_sim.get(relationship.a_tag)
            child = tag_to_sim.get(relationship.b_tag)
            if parent is None or child is None:
                continue
            kind = relationship.family_relationship or "PARENT"
            if kind == "FIANCE":
                if child.fiance_id is None:
                    child.fiance_id = parent.id
                    child.fiance_name = parent.full_name
                if parent.fiance_id is None:
                    parent.fiance_id = child.id
                    parent.fiance_name = child.full_name
                continue
            if kind == "SIBLING":
                _link_siblings(parent, child)
                continue
            if kind in ("MOTHER", "FATHER", "PARENT"):
                _link_parent_child(parent, child, kind=kind, target_id=parent.id)
                children_by_parent.setdefault(relationship.a_tag, []).append(
                    relationship.b_tag
                )
            elif kind not in ("SPOUSE", "FIANCE"):
                _link_extended(child, parent, kind)

        for child_tags in children_by_parent.values():
            for child_tag in child_tags:
                sim = tag_to_sim.get(child_tag)
                if sim is None:
                    continue
                for sibling_tag in child_tags:
                    if sibling_tag == child_tag:
                        continue
                    sibling = tag_to_sim.get(sibling_tag)
                    if sibling is not None:
                        _link_siblings(sim, sibling)


def _link_cross_household_and_ancestors(
    sims: dict[int, PremadeSim],
    ancestors: dict[int, PremadeAncestor],
    catalog: Catalog,
) -> None:
    """Apply ``FAMILY_RELATIONS_FIXUP`` and cross-household ``RELATIONSHIP_MAP`` bits."""
    nodes: dict[int, PremadeSim | PremadeAncestor] = {**ancestors, **sims}

    for fixup in getattr(catalog, "family_fixups", ()) or ():
        a = nodes.get(fixup.sim_a)
        b = nodes.get(fixup.sim_b)
        if a is None or b is None:
            continue
        for flag in fixup.flags:
            kind = flag.upper()
            if kind in ("PARENT", "SECRET_PARENT"):
                _link_parent_child(a, b, kind=kind, target_id=a.id)
            elif kind == "CHILD":
                _link_parent_child(b, a, kind="PARENT", target_id=b.id)
            elif kind == "SPOUSE":
                if a.spouse_id is None:
                    a.spouse_id = b.id
                    a.spouse_name = b.full_name
                if b.spouse_id is None:
                    b.spouse_id = a.id
                    b.spouse_name = a.full_name

    marriage_bit = catalog.marriage_bit_id or 15822
    engagement_bit = catalog.engagement_bit_id or 15816
    steady_bit = catalog.steady_bit_id or 15825

    for relationship in catalog.premade_relationships:
        sim_a = nodes.get(relationship.sim_a)
        sim_b = nodes.get(relationship.sim_b)
        if sim_a is None or sim_b is None:
            continue
        for op in getattr(relationship, "bit_operations", ()) or ():
            recipient = (
                sim_a if op.recipients.casefold() == "actor" else sim_b
            )
            target = sim_b if op.targets.casefold() == "targetsim" else sim_a
            if recipient.id == target.id:
                continue
            bit_id = op.bit_id
            if bit_id == 8809 or op.is_parent_relationship:
                _link_parent_child(target, recipient, kind="PARENT", target_id=target.id)
            elif bit_id == 8805:
                _link_parent_child(recipient, target, kind="PARENT", target_id=recipient.id)
            elif bit_id == 8802:
                _link_siblings(recipient, target)
            elif bit_id == 8824:
                _link_extended(recipient, target, "STEP_SIBLING")
                _link_extended(target, recipient, "STEP_SIBLING")
            elif bit_id == 8808:
                _link_extended(recipient, target, "GRANDPARENT")
                _link_extended(target, recipient, "GRANDCHILD")
            elif bit_id == 8807:
                _link_extended(recipient, target, "GRANDCHILD")
                _link_extended(target, recipient, "GRANDPARENT")
            elif bit_id == 8829:
                _link_extended(recipient, target, "PARENTS_SIBLING")
                _link_extended(target, recipient, "SIBLINGS_CHILDREN")
            elif bit_id == 9989:
                _link_extended(recipient, target, "SIBLINGS_CHILDREN")
                _link_extended(target, recipient, "PARENTS_SIBLING")
            elif bit_id == 8826:
                _link_extended(recipient, target, "COUSIN")
                _link_extended(target, recipient, "COUSIN")
            elif bit_id == 310896:
                _link_extended(recipient, target, "ADOPTED_BY")
            elif bit_id == 310897:
                _link_extended(recipient, target, "ADOPTED")
            elif bit_id == marriage_bit:
                if recipient.spouse_id is None:
                    recipient.spouse_id = target.id
                    recipient.spouse_name = target.full_name
                if target.spouse_id is None:
                    target.spouse_id = recipient.id
                    target.spouse_name = recipient.full_name
            elif bit_id == engagement_bit and isinstance(recipient, PremadeSim) and isinstance(target, PremadeSim):
                if recipient.fiance_id is None:
                    recipient.fiance_id = target.id
                    recipient.fiance_name = target.full_name
                if target.fiance_id is None:
                    target.fiance_id = recipient.id
                    target.fiance_name = recipient.full_name
            elif bit_id == steady_bit and isinstance(recipient, PremadeSim) and isinstance(target, PremadeSim):
                if target.id not in recipient.steady_ids:
                    recipient.steady_ids.append(target.id)
                    _append_unique(recipient.steady_names, target.full_name)
                if recipient.id not in target.steady_ids:
                    target.steady_ids.append(recipient.id)
                    _append_unique(target.steady_names, recipient.full_name)

    # Derive siblings across households/generations whenever two Sims/ancestors
    # share a parent in ``parent_links`` or an unlinked parent ``target_id``.
    by_parent_id: dict[int, list[PremadeSim | PremadeAncestor]] = {}
    for node in nodes.values():
        for link in node.parent_links:
            if link.kind in _PARENT_KINDS and link.sim_id is not None:
                by_parent_id.setdefault(link.sim_id, []).append(node)
        if isinstance(node, PremadeSim):
            for link in node.unlinked_relations:
                if link.kind in ("MOTHER", "FATHER", "PARENT") and link.target_id is not None:
                    by_parent_id.setdefault(link.target_id, []).append(node)

    for group in by_parent_id.values():
        if len(group) < 2:
            continue
        for index, first in enumerate(group):
            for second in group[index + 1 :]:
                _link_siblings(first, second)


def _build_family_tree(bundle: PremadeBundle, root_id: int) -> FamilyTree:
    nodes_by_id: dict[int, PremadeSim | PremadeAncestor] = {}
    for ancestor in bundle.ancestors:
        nodes_by_id[ancestor.id] = ancestor
    for sim in bundle.sims:
        nodes_by_id[sim.id] = sim

    visited: dict[int, FamilyTreeNode] = {}
    unlinked: list[PremadeFamilyLink] = []
    queue: list[int] = [root_id]

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        source = nodes_by_id.get(current_id)
        if source is None:
            continue

        is_ancestor = isinstance(source, PremadeAncestor)
        parent_ids = [
            link.sim_id
            for link in source.parent_links
            if link.sim_id is not None and link.kind in ("MOTHER", "FATHER", "PARENT")
        ]
        secret_parent_ids = [
            link.sim_id
            for link in source.parent_links
            if link.sim_id is not None and link.kind == "SECRET_PARENT"
        ]
        child_ids = [
            link.sim_id
            for link in source.child_links
            if link.sim_id is not None
        ]
        sibling_ids = [
            link.sim_id
            for link in source.sibling_links
            if link.sim_id is not None
        ]

        if isinstance(source, PremadeSim):
            node = FamilyTreeNode(
                id=source.id,
                name=source.name,
                full_name=source.full_name,
                kind="sim",
                gender=source.gender,
                age=source.age,
                is_ghost_or_ancestor=any(
                    trait.name.lower().startswith("trait_ghost")
                    for trait in source.traits
                ),
                household_id=source.household_id,
                household_name=source.household_name,
                spouse_id=source.spouse_id,
                spouse_name=source.spouse_name,
                fiance_id=source.fiance_id,
                fiance_name=source.fiance_name,
                steady_ids=list(source.steady_ids),
                parent_ids=parent_ids,
                secret_parent_ids=secret_parent_ids,
                child_ids=child_ids,
                sibling_ids=sibling_ids,
                parent_links=list(source.parent_links),
                child_links=list(source.child_links),
                sibling_links=list(source.sibling_links),
                extended_family_links=list(source.extended_family_links),
                unlinked_relations=list(source.unlinked_relations),
            )
            for link in source.unlinked_relations:
                _append_link_unique(unlinked, link)
        else:
            node = FamilyTreeNode(
                id=source.id,
                name=source.name,
                full_name=source.full_name,
                kind="ancestor",
                gender=source.gender,
                is_ghost_or_ancestor=True,
                thumbnail=source.thumbnail,
                death_trait_id=source.death_trait_id,
                spouse_id=source.spouse_id,
                spouse_name=source.spouse_name,
                parent_ids=parent_ids,
                secret_parent_ids=secret_parent_ids,
                child_ids=child_ids,
                sibling_ids=sibling_ids,
                parent_links=list(source.parent_links),
                child_links=list(source.child_links),
                sibling_links=list(source.sibling_links),
                extended_family_links=list(source.extended_family_links),
            )

        visited[current_id] = node

        neighbors: list[int] = [
            *parent_ids,
            *secret_parent_ids,
            *child_ids,
            *sibling_ids,
        ]
        if node.spouse_id is not None:
            neighbors.append(node.spouse_id)
        if node.fiance_id is not None:
            neighbors.append(node.fiance_id)
        for ext in node.extended_family_links:
            if ext.sim_id is not None:
                neighbors.append(ext.sim_id)

        for neighbor_id in neighbors:
            if neighbor_id not in visited and neighbor_id in nodes_by_id:
                queue.append(neighbor_id)

    return FamilyTree(
        root_id=root_id,
        nodes=visited,
        unlinked_relations=unlinked,
    )


def _apply_hints(catalog: Catalog, sim: PremadeSim, member: StarterMember) -> None:
    """Fill gender/age/body/career hints that tuning does not define."""
    if sim.gender_hint is None and member.gender is not None:
        sim.gender_hint = member.gender
    if sim.age_hint is None and member.age is not None:
        sim.age_hint = member.age
    if sim.body_blend is None and member.body_blend:
        sim.body_blend = member.body_blend
    if not sim.aspiration_track_id and member.aspiration_track_id:
        sim.aspiration_track_id = member.aspiration_track_id
        sim.aspiration_track = catalog.aspiration_tracks.get(
            member.aspiration_track_id
        )
    if sim.career_id is None and member.career_id:
        sim.career_id = member.career_id
        sim.career = catalog.careers.get(member.career_id)
    if sim.career_track_id is None and member.career_track_id:
        sim.career_track_id = member.career_track_id
        sim.career_track = catalog.career_tracks.get(member.career_track_id)
    if sim.career_track_level is None and member.career_track_level is not None:
        sim.career_track_level = member.career_track_level
        sim.career_display_level = member.career_display_level
    if (
        sim.career_level_id is None
        and sim.career_track is not None
        and sim.career_track_level is not None
        and 0 <= sim.career_track_level < len(sim.career_track.level_ids)
    ):
        sim.career_level_id = sim.career_track.level_ids[sim.career_track_level]
        sim.career_level = catalog.career_levels.get(sim.career_level_id)


def _starter_sim(
    catalog: Catalog,
    household: PremadeHousehold,
    member: StarterMember,
    index: int,
) -> PremadeSim:
    traits: list[Trait] = []
    preferences: list[Preference] = []
    unknown: list[int] = []
    for trait_id in member.trait_ids:
        trait = catalog.traits.get(trait_id)
        if trait is not None:
            traits.append(trait)
            continue
        preference = catalog.preferences.get(trait_id)
        if preference is not None:
            preferences.append(preference)
            continue
        unknown.append(trait_id)

    skills = [
        SkillLevel(
            skill_id=skill_id,
            skill_name=catalog.tuning_names.get(skill_id),
            value=value,
        )
        for skill_id, value in member.skills
    ]

    career = catalog.careers.get(member.career_id) if member.career_id else None
    career_track = (
        catalog.career_tracks.get(member.career_track_id)
        if member.career_track_id
        else None
    )
    career_level_id = None
    career_level = None
    if career_track is not None and member.career_track_level is not None:
        index = member.career_track_level
        if 0 <= index < len(career_track.level_ids):
            career_level_id = career_track.level_ids[index]
            career_level = catalog.career_levels.get(career_level_id)
    aspiration_track = (
        catalog.aspiration_tracks.get(member.aspiration_track_id)
        if member.aspiration_track_id
        else None
    )

    return PremadeSim(
        id=member.sim_id or (household.id + index),
        name=_starter_sim_name(household, member),
        first_name=member.first_name,
        last_name=member.last_name,
        explicit_trait_ids=list(member.trait_ids),
        traits=traits,
        preferences=preferences,
        unknown_trait_ids=unknown,
        skills=skills,
        aspiration_track_id=member.aspiration_track_id,
        aspiration_track=aspiration_track,
        career_id=member.career_id,
        career=career,
        career_track_id=member.career_track_id,
        career_track=career_track,
        career_track_level=member.career_track_level,
        career_display_level=member.career_display_level,
        career_level_id=career_level_id,
        career_level=career_level,
        gender_hint=member.gender,
        age_hint=member.age,
        body_blend=member.body_blend,
        household_id=household.id,
        household_name=household.name,
        source=household.source,
    )


def _starter_sim_name(household: PremadeHousehold, member: StarterMember) -> str:
    household_slug = "".join(ch for ch in household.name if ch.isalnum())
    member_slug = "".join(
        ch for ch in (member.first_name + member.last_name) if ch.isalnum()
    )
    if not member_slug:
        member_slug = f"Sim{member.sim_id:016X}" if member.sim_id else "Sim"
    return f"starterSim_{household_slug or 'Household'}_{member_slug}"


def _household_display_name(name: str) -> Optional[str]:
    for prefix in ("premadeHouseholdTemplate_", "HH_Template_", "hH_Template_"):
        if name.startswith(prefix):
            return name[len(prefix) :].replace("_", " ")
    return None


def _apply_relationship_defaults(
    households,
    catalog: Catalog,
    sims: dict[int, PremadeSim] | None = None,
) -> None:
    """Fill initial friendship/romance values from household relationship defaults.

    The game calls ``household.set_default_relationships()``: family members get
    the ``FamilyMember`` default (friendship 45), spouses additionally get the
    ``Spouse`` default (romance 75), and unrelated household members get the
    ``Roommate`` default (friendship 15).

    Entries gated by ``L n="test"`` (e.g. the ``FamilyMember`` alien-awareness
    bits) are only merged when the two Sims satisfy the trait test; without
    this, every human family would incorrectly gain ``Known Alien`` bits.
    Household links are undirected, so a directional rule passes when either
    direction passes.
    """
    family = catalog.relationship_defaults.get("FamilyMember")
    spouse = catalog.relationship_defaults.get("Spouse")
    roommate = catalog.relationship_defaults.get("Roommate")

    family_friendship = _default_track_value(family, FRIENDSHIP_TRACK_ID)
    spouse_romance = _default_track_value(spouse, ROMANCE_TRACK_ID)
    roommate_friendship = _default_track_value(roommate, FRIENDSHIP_TRACK_ID)

    sims = sims or {}
    for household in households:
        tag_to_sim: dict[str, PremadeSim] = {}
        for member in household.members:
            sim = sims.get(member.sim_template_id)
            if sim is not None:
                tag_to_sim[member.tag] = sim

        for relationship in household.relationships:
            actor = tag_to_sim.get(relationship.a_tag)
            target = tag_to_sim.get(relationship.b_tag)
            if relationship.kind == "spouse":
                relationship.friendship = family_friendship
                relationship.romance = spouse_romance
                _merge_default_bits(relationship, family, actor, target)
                _merge_default_bits(relationship, spouse, actor, target)
            elif relationship.kind == "family":
                relationship.friendship = family_friendship
                relationship.romance = 0.0
                _merge_default_bits(relationship, family, actor, target)
            else:
                relationship.friendship = roommate_friendship
                _merge_default_bits(relationship, roommate, actor, target)
            _apply_bit_ranges(relationship, catalog)


def _default_track_value(default, track_id: int) -> Optional[float]:
    if default is None:
        return None
    item = default.track(track_id)
    return item.value if item is not None else None


def _merge_default_bits(
    relationship: HouseholdRelationship,
    default,
    actor: PremadeSim | None = None,
    target: PremadeSim | None = None,
) -> None:
    if default is None:
        return
    for bit_id in default.bit_ids:
        if bit_id not in relationship.bit_ids:
            relationship.bit_ids.append(bit_id)
    if not getattr(default, "conditional", None):
        return
    if actor is None or target is None:
        return
    actor_ids = _sim_trait_ids(actor)
    target_ids = _sim_trait_ids(target)
    for rule in default.conditional:
        if _rule_passes(rule, actor_ids, target_ids):
            for bit_id in rule.bit_ids:
                if bit_id not in relationship.bit_ids:
                    relationship.bit_ids.append(bit_id)


def _sim_trait_ids(sim: PremadeSim) -> set[int]:
    return {trait.id for trait in (sim.traits or []) if trait.id is not None}


def _rule_passes(rule, actor_ids: set[int], target_ids: set[int]) -> bool:
    # Household links are undirected; a directional rule (e.g. Actor knows
    # Target is alien) counts when either direction holds.
    return rule.passes(actor_ids, target_ids) or rule.passes(
        target_ids, actor_ids
    )


def _apply_bit_ranges(
    relationship: HouseholdRelationship,
    catalog: Catalog,
) -> None:
    for bit_id in relationship.bit_ids:
        item = catalog.relationship_track_ranges.get(bit_id)
        if item is None:
            continue
        if item.track_id == FRIENDSHIP_TRACK_ID:
            relationship.friendship_min = item.min_value
            relationship.friendship_max = item.max_value
        elif item.track_id == ROMANCE_TRACK_ID:
            relationship.romance_min = item.min_value
            relationship.romance_max = item.max_value


def _build_lots(
    catalog: Catalog,
    world: Optional[WorldData],
    household_id_aliases: Optional[dict[int, int]] = None,
) -> list[PremadeLot]:
    if world is None:
        return []
    household_id_aliases = household_id_aliases or {}
    lots = [
        PremadeLot(
            id=record.instance,
            lot_name=catalog.strings.get(record.lot_name_key)
            if record.lot_name_key
            else None,
            lot_description=catalog.strings.get(record.lot_description_key)
            if record.lot_description_key
            else None,
            household_name=catalog.strings.get(record.household_name_key)
            if record.household_name_key
            else None,
            household_description=catalog.strings.get(record.household_description_key)
            if record.household_description_key
            else None,
            household_id=household_id_aliases.get(
                record.household_id, record.household_id
            )
            if record.household_id
            else None,
            lot_name_key=record.lot_name_key,
            lot_description_key=record.lot_description_key,
            source=record.source,
        )
        for record in world.lots.values()
    ]
    return sorted(lots, key=lambda lot: (lot.lot_name or "").casefold())


def _build_sim(
    entry: TuningElement,
    view: TuningView,
    source: Optional[TuningSource],
    siminfo_index: dict[int, tuple],
    catalog: Catalog,
) -> PremadeSim:
    info = view.resolved_child("_sim_creation_info")

    first_name = _localized_child(view, info, "first_name") or ""
    last_name = _last_name(view, info)
    siminfo_key = _siminfo_key(view, info)

    explicit_trait_ids, random_trait_count = _traits(view)
    skills = _skills(view)
    for skill in skills:
        skill.skill_name = catalog.tuning_names.get(skill.skill_id)

    aspiration_id = view.enabled_value("primary_aspiration")
    aspiration = catalog.aspirations.get(aspiration_id) if aspiration_id else None
    aspiration_track_id: Optional[int] = None
    aspiration_track: Optional[AspirationTrack] = None
    if aspiration is None and aspiration_id is not None:
        # Some templates (e.g. EP21 Monty) store an AspirationTrack here.
        aspiration_track = catalog.aspiration_tracks.get(aspiration_id)
        if aspiration_track is not None:
            aspiration_track_id = aspiration_id
    career_level_id = view.enabled_value("career_level")
    career_level = catalog.career_levels.get(career_level_id) if career_level_id else None
    career_track = None
    career = None
    if career_level is not None and career_level.track_id:
        career_track = catalog.career_tracks.get(career_level.track_id)
        if career_track is not None:
            career = next(
                (
                    item
                    for item in catalog.careers.values()
                    if item.start_track_id == career_track.id
                    or career_track.id in item.track_ids
                ),
                None,
            )

    dynasty = _dynasty(view)
    occult_type, _occult_siminfo = _occult(view)
    pregnancy = _pregnancy(view)
    pronouns = view.text("packed_pronouns") or view.raw_text("packed_pronouns")

    siminfo_trait_ids: list[int] = []
    if siminfo_key is not None:
        found = siminfo_index.get(siminfo_key.instance)
        raw = (
            DBPF.read_entry(found[0].path, found[1])
            if found is not None
            else None
        )
        if raw:
            known = set(catalog.traits) | set(catalog.preferences)
            try:
                siminfo_trait_ids = SimInfo.parse(
                    raw, known_trait_ids=known
                ).traits
            except SimInfoError as exc:
                catalog.diagnostics.append(ExtractionIssue.from_exception(
                    "siminfo", exc, package_path=str(found[0].path),
                    resource_key=found[1].key, tuning_id=entry.instance_id,
                ))
                siminfo_trait_ids = []

    merged_ids: list[int] = []
    for trait_id in [*explicit_trait_ids, *siminfo_trait_ids]:
        if trait_id not in merged_ids:
            merged_ids.append(trait_id)

    traits: list[Trait] = []
    preferences: list[Preference] = []
    unknown: list[int] = []
    for trait_id in merged_ids:
        trait = catalog.traits.get(trait_id)
        if trait is not None:
            traits.append(trait)
            continue
        preference = catalog.preferences.get(trait_id)
        if preference is not None:
            preferences.append(preference)
            continue
        unknown.append(trait_id)

    return PremadeSim(
        id=entry.instance_id,
        name=entry.name,
        first_name=first_name,
        last_name=last_name,
        siminfo_key=siminfo_key,
        explicit_trait_ids=explicit_trait_ids,
        siminfo_trait_ids=siminfo_trait_ids,
        traits=traits,
        preferences=preferences,
        unknown_trait_ids=unknown,
        random_trait_count=random_trait_count,
        skills=skills,
        aspiration_id=aspiration_id,
        aspiration=aspiration,
        aspiration_track_id=aspiration_track_id,
        aspiration_track=aspiration_track,
        career_level_id=career_level_id,
        career_level=career_level,
        career_id=career.id if career is not None else None,
        career=career,
        career_track_id=career_track.id if career_track is not None else None,
        career_track=career_track,
        dynasty=dynasty,
        occult_type=occult_type,
        pregnancy=pregnancy,
        pronouns=pronouns,
        source=source,
    )


def _build_household(
    entry: TuningElement,
    view: TuningView,
    source: Optional[TuningSource],
) -> PremadeHousehold:
    members: list[HouseholdMember] = []
    members_element = view.resolved_child("_household_members")
    if members_element is not None:
        for unit in members_element:
            unit = view.resolve(unit)
            if unit is None:
                continue
            tag_element = _child(unit, "household_member_tag")
            tag = view.text_of(tag_element) or view.raw_text_of(tag_element) or ""
            sim_template = view.number_of(_child(unit, "sim_template"))
            if sim_template is not None:
                members.append(HouseholdMember(tag=tag, sim_template_id=sim_template))

    relationships: list[HouseholdRelationship] = []
    relationships_element = view.resolved_child("_household_relationship")
    if relationships_element is not None:
        for item in relationships_element:
            item = view.resolve(item)
            if item is None:
                continue
            x_tag = view.text_of(_child(item, "x")) or ""
            y_tag = view.text_of(_child(item, "y")) or ""
            bit_ids = _relationship_bits(view, item)
            if view.flag_of(_child(item, "is_spouse")):
                relationships.append(
                    HouseholdRelationship(
                        kind="spouse",
                        a_tag=x_tag,
                        b_tag=y_tag,
                        bit_ids=bit_ids,
                    )
                )
                continue
            if view.flag_of(_child(item, "is_parentless_sibling")):
                relationships.append(
                    HouseholdRelationship(
                        kind="family",
                        a_tag=x_tag,
                        b_tag=y_tag,
                        family_relationship="SIBLING",
                        bit_ids=bit_ids,
                    )
                )
                continue
            family_element = _child(item, "family_relationship")
            if family_element is not None:
                family = view.text_of(family_element) or view.raw_text_of(family_element)
                if (family or "").upper() == "FIANCE":
                    relationships.append(
                        HouseholdRelationship(
                            kind="fiance",
                            a_tag=x_tag,
                            b_tag=y_tag,
                            family_relationship=family,
                            bit_ids=bit_ids,
                        )
                    )
                else:
                    relationships.append(
                        HouseholdRelationship(
                            kind="family",
                            a_tag=x_tag,
                            b_tag=y_tag,
                            family_relationship=family,
                            bit_ids=bit_ids,
                        )
                    )
            elif bit_ids:
                relationships.append(
                    HouseholdRelationship(
                        kind="relationship",
                        a_tag=x_tag,
                        b_tag=y_tag,
                        bit_ids=bit_ids,
                    )
                )

    return PremadeHousehold(
        id=entry.instance_id,
        name=entry.name,
        members=members,
        relationships=relationships,
        hidden=view.flag("_hidden"),
        townie_street=view.text("_townie_street") or view.raw_text("_townie_street"),
        funds=view.number("_household_funds"),
        source=source,
    )


def _build_ancestor(
    entry: TuningElement,
    view: TuningView,
    source: Optional[TuningSource],
) -> PremadeAncestor:
    variant_type, payload = view.variant("full_name")
    full_name = view.text_of(payload) if variant_type == "enabled" else None
    thumb_type, thumb_payload = view.variant("thumbnail")
    thumbnail = (
        (view.text_of(thumb_payload) or view.raw_text_of(thumb_payload))
        if thumb_type in (None, "enabled")
        else None
    )
    return PremadeAncestor(
        id=entry.instance_id,
        name=entry.name,
        full_name=full_name or entry.name,
        gender=view.enum("gender"),
        death_trait_id=view.enabled_value("death_trait"),
        thumbnail=thumbnail,
        source=source,
    )


# ----------------------------------------------------------------------
# field helpers
# ----------------------------------------------------------------------
def _child(element, name: str):
    if element is None:
        return None
    return next((child for child in element if child.get("n") == name), None)


def _relationship_bits(view: TuningView, item) -> list[int]:
    element = _child(item, "relationship_bits")
    if element is None:
        return []
    resolved = view.resolve(element)
    if resolved is None:
        return []
    bit_ids: list[int] = []
    for child in resolved:
        number = view.number_of(child)
        if number is not None and number not in bit_ids:
            bit_ids.append(number)
    return bit_ids


def _localized_child(view: TuningView, element, name: str) -> Optional[str]:
    return view.text_of(_child(element, name))


def _last_name(view: TuningView, info) -> str:
    element = _child(info, "last_name")
    if element is None:
        return ""
    resolved = view.resolve(element)
    if resolved is None:
        return ""

    if resolved.tag == "V":
        variant = resolved.get("t")
        if variant == "no_last_name":
            return ""
        if variant == "specify_last_name":
            value = _child(resolved, "specify_last_name")
            return view.text_of(value) or ""
        return ""

    return view.text_of(resolved) or view.raw_text_of(resolved) or ""


def _siminfo_key(view: TuningView, info) -> Optional[ResourceKey]:
    element = _child(info, "resource_key")
    if element is None:
        return None
    raw = view.raw_text_of(element)
    return parse_resource_key(raw)


def _traits(view: TuningView) -> tuple[list[int], Optional[int]]:
    element = view.resolved_child("_traits")
    if element is None:
        return [], None

    explicit_element = _child(element, "explicit")
    explicit_element = view.resolve(explicit_element)
    ids: list[int] = []
    if explicit_element is not None:
        items = list(explicit_element) if explicit_element.tag == "L" else [explicit_element]
        for item in items:
            number = view.number_of(item)
            if number is not None:
                ids.append(number)
    elif element.tag == "L":
        for item in element:
            number = view.number_of(item)
            if number is not None:
                ids.append(number)

    random_element = _child(element, "num_random")
    random_count = view.number_of(random_element) if random_element is not None else None
    return ids, random_count


def _skills(view: TuningView) -> list[SkillLevel]:
    element = view.resolved_child("_skills")
    if element is None:
        return []

    explicit_element = _child(element, "explicit")
    resolved = view.resolve(explicit_element)
    explicit_element = resolved if resolved is not None else element
    items: Iterable
    if explicit_element.tag == "L":
        items = list(explicit_element)
    elif explicit_element.tag == "U":
        items = [explicit_element]
    else:
        items = []

    skills: list[SkillLevel] = []
    for item in items:
        unit = view.resolve(item)
        if unit is None or unit.tag != "U":
            continue
        skill_id = view.number_of(_child(unit, "skill"))
        if skill_id is None:
            continue
        range_element = _child(unit, "range")
        range_element = view.resolve(range_element)
        level = minimum = maximum = ideal = None
        if range_element is not None and range_element.tag == "U":
            ideal = view.number_of(_child(range_element, "ideal_value"))
            minimum = view.number_of(_child(range_element, "min_value"))
            maximum = view.number_of(_child(range_element, "max_value"))
            level = ideal or minimum or maximum
        elif range_element is not None:
            level = view.number_of(range_element)
        skills.append(
            SkillLevel(
                skill_id=skill_id,
                level=level,
                min_value=minimum,
                max_value=maximum,
                ideal_value=ideal,
            )
        )
    return skills


def _dynasty(view: TuningView) -> dict:
    variant_type, payload = view.variant("dynasty")
    if variant_type != "enabled" or payload is None:
        return {}
    if payload.tag != "U":
        return {}
    return {
        "seed": view.number_of(_child(payload, "seed")),
        "is_head": view.flag_of(_child(payload, "is_head")),
        "is_heir": view.flag_of(_child(payload, "is_heir")),
        "is_black_sheep": view.flag_of(_child(payload, "is_black_sheep")),
    }


def _occult(view: TuningView) -> tuple[Optional[str], Optional[ResourceKey]]:
    variant_type, payload = view.variant("occult")
    if variant_type != "enabled" or payload is None or payload.tag != "U":
        return None, None
    occult_type_element = _child(payload, "occult_type")
    occult_type = view.text_of(occult_type_element) or view.raw_text_of(
        occult_type_element
    )
    siminfo_element = _child(payload, "occult_sim_info")
    return occult_type, parse_resource_key(view.raw_text_of(siminfo_element))


def _pregnancy(view: TuningView) -> dict:
    variant_type, payload = view.variant("pregnancy")
    if variant_type != "enabled" or payload is None or payload.tag != "U":
        return {}
    return {
        "other_parent": view.number_of(_child(payload, "other_parent")),
        "origin": view.text_of(_child(payload, "origin"))
        or view.raw_text_of(_child(payload, "origin")),
        "progress": view.number_of(_child(payload, "progress")),
    }


def parse_resource_key(text: Optional[str]) -> Optional[ResourceKey]:
    if not text:
        return None
    parts = text.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        return ResourceKey(
            type_id=int(parts[0], 16),
            group=int(parts[1], 16),
            instance=int(parts[2], 16),
        )
    except ValueError:
        return None
