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

from ..core import ResourceKey, TuningElement
from ..installation import Installation
from ..siminfo import SimInfo, SimInfoError
from .models import (
    Aspiration,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    Preference,
    SkillLevel,
    Trait,
    TuningSource,
)
from .values import TuningView
from .worlds import StarterMember, WorldData

__all__ = [
    "PremadeSim",
    "PremadeHousehold",
    "PremadeAncestor",
    "PremadeLot",
    "HouseholdMember",
    "HouseholdRelationship",
    "PremadeBundle",
    "build_premades",
    "parse_resource_key",
]


@dataclass
class PremadeLot:
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
class HouseholdMember:
    tag: str
    sim_template_id: int
    sim_name: Optional[str] = None
    full_name: Optional[str] = None


@dataclass
class HouseholdRelationship:
    kind: str
    a_tag: str
    b_tag: str
    family_relationship: Optional[str] = None


@dataclass
class PremadeHousehold:
    id: int
    name: str
    members: list[HouseholdMember] = field(default_factory=list)
    relationships: list[HouseholdRelationship] = field(default_factory=list)
    hidden: bool = False
    townie_street: Optional[str] = None
    funds: Optional[int] = None
    source: Optional[TuningSource] = None

    @property
    def member_ids(self) -> list[int]:
        return [member.sim_template_id for member in self.members]

    def __repr__(self) -> str:
        return f"PremadeHousehold({self.name!r}, members={len(self.members)})"


@dataclass
class PremadeAncestor:
    id: int
    name: str
    full_name: str
    gender: Optional[str] = None
    death_trait_id: Optional[int] = None
    thumbnail: Optional[str] = None
    source: Optional[TuningSource] = None

    def __repr__(self) -> str:
        return f"PremadeAncestor({self.full_name!r})"


@dataclass
class PremadeSim:
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
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    siblings: list[str] = field(default_factory=list)
    extended_family: list[str] = field(default_factory=list)
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

    def __repr__(self) -> str:
        return f"PremadeSim({self.full_name!r}, traits={len(self.traits)})"


@dataclass
class PremadeBundle:
    sims: list[PremadeSim] = field(default_factory=list)
    households: list[PremadeHousehold] = field(default_factory=list)
    ancestors: list[PremadeAncestor] = field(default_factory=list)
    lots: list[PremadeLot] = field(default_factory=list)
    sims_by_name: dict[str, PremadeSim] = field(default_factory=dict, repr=False)
    households_by_name: dict[str, PremadeHousehold] = field(
        default_factory=dict, repr=False
    )
    lots_by_name: dict[str, PremadeLot] = field(default_factory=dict, repr=False)

    def sim(self, key: str | int) -> Optional[PremadeSim]:
        if isinstance(key, int):
            return next((sim for sim in self.sims if sim.id == key), None)
        return self.sims_by_name.get(key)

    def household(self, key: str | int) -> Optional[PremadeHousehold]:
        if isinstance(key, int):
            return next((hh for hh in self.households if hh.id == key), None)
        return self.households_by_name.get(key)

    def lot(self, key: str | int) -> Optional[PremadeLot]:
        if isinstance(key, int):
            return next((lot for lot in self.lots if lot.id == key), None)
        return self.lots_by_name.get(key)

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
) -> PremadeBundle:
    sims: dict[int, PremadeSim] = {}
    households: dict[int, PremadeHousehold] = {}
    ancestors: dict[int, PremadeAncestor] = {}

    for instance_id, entry in entries.items():
        view = TuningView(entry, catalog.strings)
        source = sources.get(instance_id)
        try:
            if entry.cls == "PremadeSimTemplate":
                sims[instance_id] = _build_sim(
                    entry, view, source, installation, catalog
                )
            elif entry.cls == "PremadeHouseholdTemplate":
                households[instance_id] = _build_household(entry, view, source)
            elif entry.cls == "TunablePremadeAncestor":
                ancestors[instance_id] = _build_ancestor(entry, view, source)
        except Exception as exc:
            catalog.errors.append(f"{entry.name} ({entry.cls}): {exc}")

    for household in households.values():
        for member in household.members:
            sim = sims.get(member.sim_template_id)
            if sim is not None:
                member.sim_name = sim.name
                member.full_name = sim.full_name
                sim.household_id = household.id
                sim.household_name = household.name

    if world is not None:
        aliases = _merge_world(catalog, sims, households, world)
    else:
        aliases = {}

    bundle = PremadeBundle(
        sims=sorted(sims.values(), key=lambda sim: sim.full_name.casefold()),
        households=sorted(households.values(), key=lambda hh: hh.name.casefold()),
        ancestors=sorted(ancestors.values(), key=lambda anc: anc.full_name.casefold()),
        lots=_build_lots(catalog, world),
    )
    for sim in bundle.sims:
        bundle.sims_by_name.setdefault(sim.name, sim)
        bundle.sims_by_name.setdefault(sim.full_name, sim)
    for household in bundle.households:
        bundle.households_by_name.setdefault(household.name, household)
        display_name = _household_display_name(household.name)
        if display_name:
            bundle.households_by_name.setdefault(display_name, household)
    for alias, household in aliases.items():
        bundle.households_by_name.setdefault(alias, household)
    for lot in bundle.lots:
        if lot.lot_name:
            bundle.lots_by_name.setdefault(lot.lot_name, lot)
    return bundle


def _merge_world(
    catalog: Catalog,
    sims: dict[int, PremadeSim],
    households: dict[int, PremadeHousehold],
    world: WorldData,
) -> dict[str, PremadeHousehold]:
    """Merge ``0xB3C438F0`` households into the tuning-derived population.

    A legacy household is skipped when tuning already defines every one of its
    members (that is the case for Goth, Landgraabs and Zest, which have both a
    ``PremadeHouseholdTemplate`` and a starter-save resource).  Partially
    covered households link the existing tuning Sims and add the rest.

    Returns aliases: the resource's household name for households that already
    existed under a tuning name.
    """
    aliases: dict[str, PremadeHousehold] = {}
    by_name: dict[str, PremadeSim] = {}
    for sim in sims.values():
        if sim.full_name:
            by_name.setdefault(sim.full_name.casefold(), sim)

    tuning_by_members = {
        frozenset(member.full_name.casefold() for member in household.members if member.full_name): household
        for household in households.values()
        if household.members
    }
    taken_names = {household.name.casefold() for household in households.values()}

    for record in sorted(
        world.households.values(), key=lambda item: (item.name.casefold(), item.instance)
    ):
        if not record.members:
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

    return aliases


def _link_starter_family(
    household: Optional[PremadeHousehold],
    members: list[StarterMember],
    sim_by_tag: dict[str, PremadeSim],
) -> None:
    """Attach spouse/parent/child/sibling links from ``0xB3C438F0``.

    The resource stores the spouse in member field 15 and ancestor relations in
    ``gameplay.14`` as ``(relation_type, target_sim_id)`` pairs.  ``None`` for
    ``household`` means the tuning household already owns the relationship list
    (Goth/Landgraabs/Zest); only the Sim-level fields are filled then.
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

    parent_links: list[tuple[str, str, str]] = []
    for index, member in enumerate(members, start=1):
        child_tag = f"household_member_{index}"
        for relation in member.relations:
            parent_tag = tag_by_id.get(relation.target_id)
            if not parent_tag:
                continue
            parent_links.append((parent_tag, child_tag, relation.kind))
            if household is not None:
                household.relationships.append(
                    HouseholdRelationship(
                        kind="family",
                        a_tag=parent_tag,
                        b_tag=child_tag,
                        family_relationship=relation.kind,
                    )
                )

    for parent_tag, child_tag, kind in parent_links:
        parent = sim_by_tag.get(parent_tag)
        child = sim_by_tag.get(child_tag)
        if parent is None or child is None:
            continue
        if kind in ("MOTHER", "FATHER", "PARENT"):
            _append_unique(child.parents, parent.full_name)
            _append_unique(parent.children, child.full_name)
        else:
            _append_unique(child.extended_family, parent.full_name)

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

    children_by_parent: dict[str, list[str]] = {}
    for parent_tag, child_tag, kind in parent_links:
        if kind in ("MOTHER", "FATHER", "PARENT"):
            children_by_parent.setdefault(parent_tag, []).append(child_tag)

    for child_tags in children_by_parent.values():
        for child_tag in child_tags:
            sim = sim_by_tag.get(child_tag)
            if sim is None:
                continue
            for sibling_tag in child_tags:
                if sibling_tag == child_tag:
                    continue
                sibling = sim_by_tag.get(sibling_tag)
                if sibling is not None:
                    _append_unique(sim.siblings, sibling.full_name)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


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


def _build_lots(catalog: Catalog, world: Optional[WorldData]) -> list[PremadeLot]:
    if world is None:
        return []
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
            household_id=record.household_id,
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
    installation: Installation,
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

    dynasty = _dynasty(view)
    occult_type, _occult_siminfo = _occult(view)
    pregnancy = _pregnancy(view)
    pronouns = view.text("packed_pronouns") or view.raw_text("packed_pronouns")

    siminfo_trait_ids: list[int] = []
    if siminfo_key is not None:
        raw = installation.find_siminfo(siminfo_key.instance)
        if raw:
            known = set(catalog.traits) | set(catalog.preferences)
            try:
                siminfo_trait_ids = SimInfo.parse(
                    raw, known_trait_ids=known
                ).traits
            except SimInfoError:
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
        career_level=(
            catalog.career_levels.get(career_level_id) if career_level_id else None
        ),
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
            if view.flag_of(_child(item, "is_spouse")):
                relationships.append(
                    HouseholdRelationship(kind="spouse", a_tag=x_tag, b_tag=y_tag)
                )
                continue
            family_element = _child(item, "family_relationship")
            if family_element is not None:
                family = view.text_of(family_element) or view.raw_text_of(family_element)
                relationships.append(
                    HouseholdRelationship(
                        kind="family",
                        a_tag=x_tag,
                        b_tag=y_tag,
                        family_relationship=family,
                    )
                )

    return PremadeHousehold(
        id=entry.instance_id,
        name=entry.name,
        members=members,
        relationships=relationships,
        hidden=view.flag("_hidden"),
        townie_street=view.text("_townie_street") or view.raw_text("_townie_street"),
        source=source,
    )


def _build_ancestor(
    entry: TuningElement,
    view: TuningView,
    source: Optional[TuningSource],
) -> PremadeAncestor:
    variant_type, payload = view.variant("full_name")
    full_name = view.text_of(payload) if variant_type == "enabled" else None
    return PremadeAncestor(
        id=entry.instance_id,
        name=entry.name,
        full_name=full_name or entry.name,
        gender=view.enum("gender"),
        death_trait_id=view.number("death_trait"),
        thumbnail=view.text("thumbnail"),
        source=source,
    )


# ----------------------------------------------------------------------
# field helpers
# ----------------------------------------------------------------------
def _child(element, name: str):
    if element is None:
        return None
    return next((child for child in element if child.get("n") == name), None)


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
