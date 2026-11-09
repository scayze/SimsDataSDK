"""Extract pre-made Sims, households, and ancestors without a save file.

In The Sims 4 the concrete pre-made population is defined by tuning:

* ``PremadeSimTemplate`` — name, referenced ``.siminfo`` resource, explicit
  traits/skills, primary aspiration, career level, dynasty and occult data.
* ``PremadeHouseholdTemplate`` — household members and their relationships.
* ``TunablePremadeAncestor`` — ancestors used to build family trees.

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
    CareerLevel,
    Catalog,
    Preference,
    SkillLevel,
    Trait,
    TuningSource,
)
from .values import TuningView

__all__ = [
    "PremadeSim",
    "PremadeHousehold",
    "PremadeAncestor",
    "HouseholdMember",
    "HouseholdRelationship",
    "PremadeBundle",
    "build_premades",
    "parse_resource_key",
]


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
        for trait in self.traits:
            if trait.name in ("trait_GenderMale", "trait_GenderFemale"):
                return trait.name[len("trait_Gender") :].upper()
        return None

    def __repr__(self) -> str:
        return f"PremadeSim({self.full_name!r}, traits={len(self.traits)})"


@dataclass
class PremadeBundle:
    sims: list[PremadeSim] = field(default_factory=list)
    households: list[PremadeHousehold] = field(default_factory=list)
    ancestors: list[PremadeAncestor] = field(default_factory=list)
    sims_by_name: dict[str, PremadeSim] = field(default_factory=dict, repr=False)
    households_by_name: dict[str, PremadeHousehold] = field(
        default_factory=dict, repr=False
    )

    def sim(self, key: str | int) -> Optional[PremadeSim]:
        if isinstance(key, int):
            return next((sim for sim in self.sims if sim.id == key), None)
        return self.sims_by_name.get(key)

    def household(self, key: str | int) -> Optional[PremadeHousehold]:
        if isinstance(key, int):
            return next((hh for hh in self.households if hh.id == key), None)
        return self.households_by_name.get(key)

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

    bundle = PremadeBundle(
        sims=sorted(sims.values(), key=lambda sim: sim.full_name.casefold()),
        households=sorted(households.values(), key=lambda hh: hh.name.casefold()),
        ancestors=sorted(ancestors.values(), key=lambda anc: anc.full_name.casefold()),
    )
    for sim in bundle.sims:
        bundle.sims_by_name.setdefault(sim.name, sim)
        bundle.sims_by_name.setdefault(sim.full_name, sim)
    for household in bundle.households:
        bundle.households_by_name[household.name] = household
    return bundle


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
        aspiration=catalog.aspirations.get(aspiration_id) if aspiration_id else None,
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
