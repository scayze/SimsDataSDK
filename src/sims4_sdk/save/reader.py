"""Reader for The Sims 4 save files (``Slot_*.save``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from ..catalog.models import Catalog
from ..core import DBPF
from .enums import (
    AGE_NAMES,
    FAMILY_RELATION_NAMES,
    GENDER_NAMES,
    OCCULT_FLAGS,
    SPECIES_NAMES,
    name_for,
    names_for_flags,
)
from .models import (
    SaveAccount,
    SaveFile,
    SaveNeighborhood,
    SaveSlot,
    SaveZone,
    SavedCareer,
    SavedCareerHistory,
    SavedFamilyRelation,
    SavedHousehold,
    SavedMilestone,
    SavedRelationship,
    SavedRelationshipTrack,
    SavedRelationshipTrope,
    SavedSim,
    SavedSkill,
    SavedStatistic,
    SavedTimedAspiration,
)
from .protobuf import ProtobufError, decode
from .schema import SCHEMAS

__all__ = [
    "SaveError",
    "read_save",
    "sim_from_dict",
    "read_save_resource",
    "SAVE_RESOURCE_TYPE",
]

SAVE_RESOURCE_TYPE = 0x0000000D


class SaveError(ValueError):
    """Raised when a save file cannot be parsed."""


def read_save(path: str | Path, catalog: Optional[Catalog] = None) -> SaveFile:
    """Read a ``.save`` file, optionally resolving IDs against a catalog."""
    path = Path(path)
    package = DBPF(path)
    entry = next(
        (entry for entry in package.entries if entry.key.type_id == SAVE_RESOURCE_TYPE),
        None,
    )
    if entry is None:
        raise SaveError(f"{path.name}: no SaveGameData resource (0x0000000D)")
    try:
        data = package.read_resource(entry)
        root = decode(data, "SaveGameData", SCHEMAS)
    except ProtobufError as exc:
        raise SaveError(f"{path.name}: {exc}") from exc
    return _build_save(path, root, catalog)


def read_save_resource(data: bytes, catalog: Optional[Catalog] = None, name: str = "<memory>") -> SaveFile:
    """Read an already-extracted SaveGameData payload."""
    root = decode(data, "SaveGameData", SCHEMAS)
    return _build_save(Path(name), root, catalog)


def _build_save(path: Path, root: Mapping[str, Any], catalog: Optional[Catalog]) -> SaveFile:
    slot = _slot(root.get("save_slot", {}))
    account = _account(root.get("account", {}))

    zones = {}
    for raw_zone in root.get("zones", []):
        zone_id = raw_zone.get("zone_id")
        if zone_id is None:
            continue
        zones[zone_id] = SaveZone(
            zone_id=zone_id,
            name=raw_zone.get("name"),
            world_id=raw_zone.get("world_id"),
            lot_id=raw_zone.get("lot_id"),
            household_id=raw_zone.get("household_id"),
            neighborhood_id=raw_zone.get("neighborhood_id"),
            description=raw_zone.get("description"),
        )

    neighborhoods = {}
    for raw_neighborhood in root.get("neighborhoods", []):
        neighborhood_id = raw_neighborhood.get("neighborhood_id")
        if neighborhood_id is None:
            continue
        neighborhoods[neighborhood_id] = SaveNeighborhood(
            neighborhood_id=neighborhood_id,
            name=raw_neighborhood.get("name"),
            region_id=raw_neighborhood.get("region_id"),
            description=raw_neighborhood.get("description"),
        )

    raw_sims = root.get("sims", [])
    names: dict[int, str] = {}
    for raw_sim in raw_sims:
        sim_id = raw_sim.get("sim_id")
        if sim_id:
            names[sim_id] = f"{raw_sim.get('first_name', '')} {raw_sim.get('last_name', '')}".strip()

    sims: dict[int, SavedSim] = {}
    for raw_sim in raw_sims:
        sim_id = raw_sim.get("sim_id")
        if not sim_id:
            continue
        sim = sim_from_dict(raw_sim, catalog, names)
        sims[sim_id] = sim

    households: dict[int, SavedHousehold] = {}
    for raw_household in root.get("households", []):
        household_id = raw_household.get("household_id")
        if not household_id:
            continue
        household = _household_from_dict(raw_household, sims)
        households[household_id] = household

    for household in households.values():
        for sim_id in household.member_ids:
            sim = sims.get(sim_id)
            if sim is not None:
                sim.household_name = household.name

    _link_family(sims)
    _link_special_relationships(sims, catalog)

    return SaveFile(
        path=path,
        slot=slot,
        account=account,
        sims=sims,
        households=households,
        zones=zones,
        neighborhoods=neighborhoods,
        raw=dict(root),
    )


def _slot(raw: Mapping[str, Any]) -> SaveSlot:
    return SaveSlot(
        slot_id=raw.get("slot_id"),
        slot_name=raw.get("slot_name"),
        timestamp=raw.get("timestamp"),
        active_household_id=raw.get("active_household_id"),
        nucleus_id=raw.get("nucleus_id"),
        s4_guid_seed=raw.get("s4_guid_seed"),
        compatibility_version=raw.get("compatibility_version"),
        last_neighborhood=raw.get("last_neighborhood"),
        last_zone=raw.get("last_zone"),
    )


def _account(raw: Mapping[str, Any]) -> SaveAccount:
    return SaveAccount(
        email=raw.get("email"),
        client_version=raw.get("client_version"),
        save_slot_id=raw.get("save_slot_id"),
        created=raw.get("created"),
        last_login=raw.get("last_login"),
        number_of_saves=raw.get("number_of_saves"),
        number_of_saves_mods=raw.get("number_of_saves_mods"),
        number_of_saves_script_mods=raw.get("number_of_saves_script_mods"),
    )


def sim_from_dict(
    data: Mapping[str, Any],
    catalog: Optional[Catalog] = None,
    names: Optional[Mapping[int, str]] = None,
) -> SavedSim:
    """Build a :class:`SavedSim` from a decoded ``SimData`` message."""
    names = names or {}
    attributes = data.get("attributes", {}) or {}
    gameplay = data.get("gameplay_data", {}) or {}

    trait_ids = _as_list(attributes.get("trait_tracker", {}).get("trait_ids"))
    traits = []
    preferences = []
    unknown_trait_ids = []
    for trait_id in trait_ids:
        trait = catalog.traits.get(trait_id) if catalog else None
        preference = catalog.preferences.get(trait_id) if catalog else None
        if trait is not None:
            traits.append(trait)
        elif preference is not None:
            preferences.append(preference)
        else:
            unknown_trait_ids.append(trait_id)

    aspiration_track_id = data.get("primary_aspiration")
    aspiration_track = (
        catalog.aspiration_tracks.get(aspiration_track_id)
        if catalog and aspiration_track_id
        else None
    )

    careers = _careers(attributes.get("sim_careers", {}) or {}, catalog)
    skills = _skills(attributes.get("skill_tracker", {}) or {}, catalog)
    relationships = _relationships(
        attributes.get("relationship_tracker", {}) or {}, catalog, names
    )
    genealogy = attributes.get("genealogy_tracker", {}) or {}
    parents, siblings, extended = _family_relations(genealogy, names)
    tropes = _relationship_tropes(genealogy, catalog, names)

    event_data = attributes.get("event_data_tracker", {}) or {}
    milestone_tracker = gameplay.get("developmental_milestone_tracker", {}) or {}
    milestones = _milestones(milestone_tracker, catalog)
    timed_aspirations = _timed_aspirations(event_data.get("timed_aspirations", []), catalog)

    occult_raw = (attributes.get("occult_tracker", {}) or {}).get("occult_types", 0) or 0
    death = dict(attributes.get("death_tracker", {}) or {})
    pregnancy = dict(attributes.get("pregnancy_tracker", {}) or {})
    if data.get("pregnancy_progress"):
        pregnancy["progress"] = data["pregnancy_progress"]
    degree = dict(attributes.get("degree_tracker", {}) or {})
    favorites = list((attributes.get("favorites_tracker", {}) or {}).get("favorites", []) or [])
    statistics = _statistics(attributes.get("statistics_tracker", {}) or {}, catalog)

    sim_id = data.get("sim_id", 0)
    first_name = data.get("first_name", "") or ""
    last_name = data.get("last_name", "") or ""
    age_raw = data.get("age")
    gender_raw = data.get("gender")
    species_raw = data.get("extended_species")

    return SavedSim(
        sim_id=sim_id,
        first_name=first_name,
        last_name=last_name,
        nucleus_id=data.get("nucleus_id"),
        household_id=data.get("household_id"),
        household_name=data.get("household_name"),
        zone_id=data.get("zone_id"),
        world_id=data.get("world_id"),
        age_raw=age_raw,
        age=AGE_NAMES.get(age_raw) if age_raw is not None else None,
        gender_raw=gender_raw,
        gender=GENDER_NAMES.get(gender_raw) if gender_raw is not None else None,
        species_raw=species_raw,
        species=SPECIES_NAMES.get(species_raw) if species_raw is not None else None,
        occult_raw=occult_raw,
        occult=names_for_flags(occult_raw, OCCULT_FLAGS),
        primary_aspiration_track_id=aspiration_track_id,
        aspiration_track=aspiration_track,
        traits=traits,
        preferences=preferences,
        unknown_trait_ids=unknown_trait_ids,
        careers=careers,
        skills=skills,
        relationships=relationships,
        spouse_id=data.get("significant_other") or None,
        fiance_id=data.get("fiance") or None,
        tropes=tropes,
        parents=parents,
        siblings=siblings,
        extended_family=extended,
        milestones=milestones,
        objective_ids=_as_list(event_data.get("objectives_completed")),
        completed_milestone_ids=_as_list(event_data.get("milestones_completed")),
        timed_aspirations=timed_aspirations,
        pregnancy=pregnancy,
        degree=degree,
        death=death,
        favorites=favorites,
        statistics=statistics,
        raw=dict(data),
    )


def _careers(raw: Mapping[str, Any], catalog: Optional[Catalog]) -> list[SavedCareer]:
    careers: list[SavedCareer] = []
    history_by_career: dict[tuple[int, int], list[SavedCareerHistory]] = {}
    for entry in raw.get("career_history", []) or []:
        key = (entry.get("career_uid", 0), entry.get("track_uid", 0))
        history_by_career.setdefault(key, []).append(
            SavedCareerHistory(
                career_id=entry.get("career_uid", 0),
                track_id=entry.get("track_uid", 0),
                track_level=entry.get("track_level", 0),
                user_display_level=entry.get("user_display_level"),
                highest_level=entry.get("highest_level"),
                daily_pay=entry.get("daily_pay"),
                days_worked=entry.get("days_worked"),
            )
        )

    for entry in raw.get("careers", []) or []:
        career_id = entry.get("career_uid", 0)
        track_id = entry.get("track_uid", 0)
        track_level = entry.get("track_level", 0) or 0
        career = catalog.careers.get(career_id) if catalog else None
        track = catalog.career_tracks.get(track_id) if catalog else None
        level_id = None
        level = None
        if track is not None and track.level_ids:
            index = track_level
            if not 0 <= index < len(track.level_ids):
                index = max(0, min(track_level - 1, len(track.level_ids) - 1))
            level_id = track.level_ids[index]
            level = catalog.career_levels.get(level_id) if catalog else None
        careers.append(
            SavedCareer(
                career_id=career_id,
                track_id=track_id,
                track_level=track_level,
                career=career,
                track=track,
                level_id=level_id,
                level=level,
                user_display_level=entry.get("user_display_level"),
                pay_per_hour=level.pay_per_hour if level is not None else None,
                pending_promotion=bool(entry.get("pending_promotion")),
                base_performance=entry.get("base_work_performance"),
                positive_performance=entry.get("positive_work_performance"),
                negative_performance=entry.get("negative_work_performance"),
                history=history_by_career.get((career_id, track_id), []),
            )
        )
    return careers


def _skills(raw: Mapping[str, Any], catalog: Optional[Catalog]) -> list[SavedSkill]:
    skills: list[SavedSkill] = []
    for entry in raw.get("skills", []) or []:
        skill_id = entry.get("name_hash", 0)
        skills.append(
            SavedSkill(
                skill_id=skill_id,
                name=catalog.tuning_names.get(skill_id) if catalog else None,
                tuning_class=catalog.tuning_classes.get(skill_id) if catalog else None,
                value=entry.get("value", 0.0),
            )
        )
    return skills


def _relationships(
    raw: Mapping[str, Any],
    catalog: Optional[Catalog],
    names: Mapping[int, str],
) -> list[SavedRelationship]:
    relationships: list[SavedRelationship] = []
    for entry in raw.get("relationships", []) or []:
        target_id = entry.get("target_id", 0)
        bits = _as_list(entry.get("bits"))
        bit_names = []
        if catalog:
            bit_names = [
                catalog.relationship_bits[bit_id].display_name
                for bit_id in bits
                if bit_id in catalog.relationship_bits
            ]
        tracks = []
        for track in entry.get("tracks", []) or []:
            track_id = track.get("track_id", 0)
            tracks.append(
                SavedRelationshipTrack(
                    track_id=track_id,
                    value=track.get("value", 0.0),
                    name=catalog.tuning_names.get(track_id) if catalog else None,
                    visible=bool(track.get("visible", True)),
                )
            )
        relationships.append(
            SavedRelationship(
                target_id=target_id,
                target_name=names.get(target_id),
                value=entry.get("value", 0.0),
                bits=bits,
                bit_names=bit_names,
                track_values=tracks,
                last_update_time=entry.get("last_update_time"),
            )
        )
    return relationships


def _family_relations(
    raw: Mapping[str, Any],
    names: Mapping[int, str],
) -> tuple[list[SavedFamilyRelation], list[SavedFamilyRelation], list[SavedFamilyRelation]]:
    parents: list[SavedFamilyRelation] = []
    siblings: list[SavedFamilyRelation] = []
    extended: list[SavedFamilyRelation] = []
    for entry in raw.get("family_relations", []) or []:
        target_id = entry.get("sim_id", 0)
        kind = FAMILY_RELATION_NAMES.get(entry.get("relation_type"), "UNKNOWN")
        relation = SavedFamilyRelation(kind=kind, sim_id=target_id, name=names.get(target_id))
        if kind in ("MOTHER", "FATHER", "PARENT"):
            parents.append(relation)
        elif kind == "SIBLING":
            siblings.append(relation)
        else:
            extended.append(relation)
    return parents, siblings, extended


def _relationship_tropes(
    raw: Mapping[str, Any],
    catalog: Optional[Catalog],
    names: Mapping[int, str],
) -> list[SavedRelationshipTrope]:
    """Decode family/romance dynamics stored in the genealogy tracker."""
    tropes: list[SavedRelationshipTrope] = []
    for entry in raw.get("relationship_tropes", []) or []:
        target_id = entry.get("sim_id", 0)
        trope_id = entry.get("trope_id", 0)
        bit = catalog.relationship_bits.get(trope_id) if catalog else None
        kind = "UNKNOWN"
        if catalog is not None:
            if trope_id in catalog.family_trope_ids:
                kind = "FAMILY"
            elif trope_id in catalog.romance_trope_ids:
                kind = "ROMANCE"
        if kind == "UNKNOWN" and bit is not None:
            if bit.name.startswith("familyTrope"):
                kind = "FAMILY"
            elif bit.name.startswith("romanceTrope"):
                kind = "ROMANCE"
        tropes.append(
            SavedRelationshipTrope(
                sim_id=target_id,
                trope_id=trope_id,
                sim_name=names.get(target_id),
                trope_name=(
                    (bit.display_name or bit.name)
                    if bit is not None
                    else (catalog.tuning_names.get(trope_id) if catalog else None)
                ),
                kind=kind,
            )
        )
    return tropes


def _milestones(raw: Mapping[str, Any], catalog: Optional[Catalog]) -> list[SavedMilestone]:
    milestones: list[SavedMilestone] = []
    for entry in [*(raw.get("active_milestones", []) or []), *(raw.get("archived_milestones", []) or [])]:
        milestone_id = entry.get("milestone_id", 0)
        milestones.append(
            SavedMilestone(
                milestone_id=milestone_id,
                milestone=catalog.milestones.get(milestone_id) if catalog else None,
                state=entry.get("state"),
                age_completed=entry.get("age_completed"),
                new_in_ui=bool(entry.get("new_in_ui")),
            )
        )
    return milestones


def _timed_aspirations(
    raw: list[Mapping[str, Any]],
    catalog: Optional[Catalog],
) -> list[SavedTimedAspiration]:
    timed = []
    for entry in raw or []:
        aspiration_id = entry.get("aspiration", 0)
        aspiration = catalog.aspirations.get(aspiration_id) if catalog else None
        timed.append(
            SavedTimedAspiration(
                aspiration_id=aspiration_id,
                name=aspiration.name if aspiration is not None else (
                    catalog.tuning_names.get(aspiration_id) if catalog else None
                ),
                end_time=entry.get("end_time"),
                completed=bool(entry.get("completed")),
            )
        )
    return timed


def _statistics(raw: Mapping[str, Any], catalog: Optional[Catalog]) -> list[SavedStatistic]:
    statistics = []
    for entry in raw.get("statistics", []) or []:
        statistic_id = entry.get("name_hash", 0)
        statistics.append(
            SavedStatistic(
                statistic_id=statistic_id,
                name=catalog.tuning_names.get(statistic_id) if catalog else None,
                value=entry.get("value", 0.0),
            )
        )
    return statistics


def _household_from_dict(
    raw: Mapping[str, Any],
    sims: Mapping[int, SavedSim],
) -> SavedHousehold:
    household_id = raw.get("household_id", 0)
    member_ids = _as_list((raw.get("sims", {}) or {}).get("ids"))
    if not member_ids:
        member_ids = [sim_id for sim_id, sim in sims.items() if sim.household_id == household_id]
    gameplay = raw.get("gameplay_data", {}) or {}
    milestone_tracker = gameplay.get("household_milestone_tracker", {}) or {}
    return SavedHousehold(
        household_id=household_id,
        name=raw.get("name"),
        money=raw.get("money"),
        home_zone=raw.get("home_zone"),
        last_played_sim_id=raw.get("last_played_sim_id"),
        creation_time=raw.get("creation_time"),
        last_modified_time=raw.get("last_modified_time"),
        is_unplayed=bool(raw.get("is_unplayed")),
        is_player=bool(raw.get("is_player")),
        hidden=bool(raw.get("hidden")),
        premade_household_id=raw.get("premade_household_id"),
        premade_household_template_id=raw.get("premade_household_template_id"),
        description=raw.get("description"),
        member_ids=member_ids,
        members=[sims[sim_id].full_name for sim_id in member_ids if sim_id in sims],
        milestones_completed=_as_list(milestone_tracker.get("milestones_completed")),
        raw=dict(raw),
    )


def _link_family(sims: Mapping[int, SavedSim]) -> None:
    """Fill spouse names, children, and sibling back-references."""
    for sim in sims.values():
        if sim.spouse_id and sim.spouse_id in sims:
            sim.spouse_name = sims[sim.spouse_id].full_name
            spouse = sims[sim.spouse_id]
            if spouse.spouse_id is None:
                spouse.spouse_id = sim.sim_id
                spouse.spouse_name = sim.full_name
        if sim.fiance_id and sim.fiance_id in sims:
            fiance = sims[sim.fiance_id]
            if fiance.fiance_id is None:
                fiance.fiance_id = sim.sim_id

    children: dict[int, dict[int, SavedFamilyRelation]] = {sim_id: {} for sim_id in sims}
    for sim in sims.values():
        for parent in sim.parents:
            if parent.sim_id in sims:
                children[parent.sim_id][sim.sim_id] = SavedFamilyRelation(
                    kind="CHILD", sim_id=sim.sim_id, name=sim.full_name
                )

    for sim in sims.values():
        sim.children = sorted(children.get(sim.sim_id, {}).values(), key=lambda rel: rel.sim_id)

    # Fill sibling relations for sims without an explicit SIBLING entry.
    for sim in sims.values():
        if sim.siblings:
            continue
        parent_ids = {parent.sim_id for parent in sim.parents}
        if not parent_ids:
            continue
        for candidate in sims.values():
            if candidate.sim_id == sim.sim_id:
                continue
            if parent_ids & {parent.sim_id for parent in candidate.parents}:
                sim.siblings.append(
                    SavedFamilyRelation(
                        kind="SIBLING", sim_id=candidate.sim_id, name=candidate.full_name
                    )
                )


def _link_special_relationships(
    sims: Mapping[int, SavedSim],
    catalog: Optional[Catalog],
) -> None:
    """Fill fiancé/steady data and derive missing links from relationship bits."""
    steady_bit = catalog.steady_bit_id if catalog is not None else None
    engagement_bit = catalog.engagement_bit_id if catalog is not None else None
    marriage_bit = catalog.marriage_bit_id if catalog is not None else None

    def bits_of(sim: SavedSim, target_id: int) -> list[int]:
        for relationship in sim.relationships:
            if relationship.target_id == target_id:
                return relationship.bits
        return []

    def has_bit(sim: SavedSim, target_id: int, bit_id: Optional[int]) -> bool:
        return bit_id is not None and bit_id in bits_of(sim, target_id)

    for sim in sims.values():
        if sim.spouse_id and sim.spouse_id in sims:
            sim.spouse_name = sims[sim.spouse_id].full_name
        if sim.fiance_id and sim.fiance_id in sims:
            sim.fiance_name = sims[sim.fiance_id].full_name
            fiance = sims[sim.fiance_id]
            if fiance.fiance_id is None:
                fiance.fiance_id = sim.sim_id
                fiance.fiance_name = sim.full_name

        # Steady partners are not stored in their own field; they are the Sims
        # whose relationship entry carries the steady relationship bit.
        steady_ids: list[int] = []
        for relationship in sim.relationships:
            target_id = relationship.target_id
            if target_id == sim.sim_id or target_id not in sims:
                continue
            if steady_bit is not None and steady_bit in relationship.bits:
                if target_id not in steady_ids:
                    steady_ids.append(target_id)
        sim.steady_ids = steady_ids
        sim.steady_names = [sims[target_id].full_name for target_id in steady_ids]

        if marriage_bit is not None:
            if sim.spouse_id is None:
                for target_id in sims:
                    if target_id != sim.sim_id and has_bit(sim, target_id, marriage_bit):
                        sim.spouse_id = target_id
                        sim.spouse_name = sims[target_id].full_name
                        break
            elif sim.spouse_name is None and sim.spouse_id in sims:
                sim.spouse_name = sims[sim.spouse_id].full_name

        if engagement_bit is not None and sim.fiance_id is None:
            for target_id in sims:
                if target_id != sim.sim_id and has_bit(sim, target_id, engagement_bit):
                    sim.fiance_id = target_id
                    sim.fiance_name = sims[target_id].full_name
                    break


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
