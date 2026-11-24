"""Build package resources from existing new-save templates."""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Optional

from .catalog.lot_registry import WorldLot
from .catalog.lot_traits import LOT_TRAITS_MODULE
from .catalog.relationships import FRIENDSHIP_TRACK_ID, RELATIONSHIPS_MODULE, ROMANCE_TRACK_ID
from .catalog.worlds import LotRecord, StarterCareer, WorldData
from .core.combined_tuning import CombinedTuning, TuningElement
from .core.dbpf import ResourceKey, write_package
from .core.fnv import fnv1_32, fnv1_64
from .core.resource_types import (
    ACTION_TUNING_TYPE_ID, LOT_MANIFEST_TYPE_ID, PREMADE_HOUSEHOLD_TYPE_ID, SIM_TEMPLATE_TYPE_ID,
    STRING_TABLE_TYPE_ID, TUNING_TYPE_ID,
)
from .core.stbl import LOCALE_CODES, StringTable
from .exceptions import Sims4SDKError
from .save.protobuf import _encode_varint, _iter_field_spans, iter_fields

__all__ = [
    "ModPackageError",
    "write_package",
    "StarterMemberEdit",
    "starter_household_override",
    "premade_template_override",
    "premade_relationship_override",
    "relationship_loot",
    "initial_lot_traits_override",
    "move_starter_household",
    "starter_household_text",
]


class ModPackageError(Sims4SDKError, ValueError):
    """A template source or override is invalid."""


def move_starter_household(
    world: WorldData, origin: WorldLot, destination: WorldLot,
) -> tuple[tuple[ResourceKey, bytes], tuple[ResourceKey, bytes]]:
    """Relocate a baked premade household between two default residential lots.

    Pass lots from the clean registry and the corresponding static world data.
    Both version 18 manifests must be included in the exported package.
    """
    if origin.lot_id == destination.lot_id:
        raise ModPackageError("origin and destination must be distinct lots")
    if (origin.occupancy, destination.occupancy) != ("occupied", "vacant"):
        raise ModPackageError("the move needs an occupied origin and a vacant destination")
    resources: list[tuple[ResourceKey, bytes]] = []
    for lot in (origin, destination):
        if lot.zone_id is not None or lot.venue_id != 28614:
            raise ModPackageError("the move needs default lots with the Residential venue")
        key = lot.manifest_key
        record = world.lot_resources.get(key)
        if (key is None or key.type_id != LOT_MANIFEST_TYPE_ID or record is None
                or record.lot_description_id != lot.lot_description_id
                or record.lot_template_id != lot.lot_template_id):
            raise ModPackageError("lot manifest does not match the supplied world data")
        if len(record.raw) != 162 or record.raw[:4] != b"\x12\0\0\0":
            raise ModPackageError("moving households requires version 18 lot manifests")
        resources.append((key, record.raw))

    source_key, source = resources[0]
    target_key, target = resources[1]
    if (source_key == target_key or source[83] != 2 or target[83] != 0
            or not origin.starter_household_id
            or struct.unpack_from("<Q", source, 122)[0] != origin.starter_household_id
            or target[114:130] != bytes(16)):
        raise ModPackageError("expected a baked starter assignment and an unassigned destination")
    # The assignment marker and household name, description, and resource ID
    # travel together. The lot template and physical location stay in place.
    cleared = source[:83] + b"\0" + source[84:114] + bytes(16) + source[130:]
    occupied = target[:83] + b"\x02" + target[84:114] + source[114:130] + target[130:]
    return (source_key, cleared), (target_key, occupied)


def starter_household_text(
    manifest: tuple[ResourceKey, bytes],
    *,
    name: str | None = None,
    description: str | None = None,
    locales: Iterable[int] | None = None,
) -> list[tuple[ResourceKey, bytes]]:
    """Set the name and description players see for a placed starter household.

    The game shows the text that the lot manifest (the house description)
    references, not the household record's inline text. This returns the
    edited manifest followed by one string table per locale that holds the
    new text. ``locales`` are locale bytes from
    :data:`~sims4_sdk.core.stbl.LOCALE_CODES`; by default every locale gets
    the same text. To move the household too, pass the destination manifest
    returned by :func:`move_starter_household`.
    """
    key, data = manifest
    if key.type_id != LOT_MANIFEST_TYPE_ID or not isinstance(data, bytes):
        raise ModPackageError("expected a lot manifest resource key and its bytes")
    if name is None and description is None:
        raise ModPackageError("supply a household name or description")
    offset = LotRecord(key.instance, raw=data).household_block_offset
    if offset is None:
        raise ModPackageError("unsupported lot manifest layout")
    if not struct.unpack_from("<Q", data, offset + 8)[0]:
        raise ModPackageError("the lot manifest has no starter household")
    codes = sorted(set(LOCALE_CODES if locales is None else locales))
    if not codes or any(code not in LOCALE_CODES for code in codes):
        raise ModPackageError("locales must be known STBL locale codes")
    namespace = f"sims4_sdk:household_text:{key.group:08x}:{key.instance:016x}"
    strings = {}
    edited = bytearray(data)
    for position, label, value in ((0, "name", name), (4, "description", description)):
        if value is None:
            continue
        string_key = fnv1_32(f"{namespace}:{label}")
        strings[string_key] = _text(value, f"household {label}",
                                    allow_empty=label == "description").decode("utf-8")
        struct.pack_into("<I", edited, offset + position, string_key)
    table = StringTable.from_entries(strings).to_bytes()
    base = fnv1_64(namespace) & 0x00FFFFFFFFFFFFFF
    return [(key, bytes(edited))] + [
        (ResourceKey(STRING_TABLE_TYPE_ID, 0, code << 56 | base), table) for code in codes
    ]


def _replace_fields(data: bytes, replacements: Mapping[int, tuple[int, int | bytes]]) -> bytes:
    """Copy untouched fields and any footer byte-for-byte."""
    remainder = dict(replacements)
    output = bytearray()
    end = 0
    for number, wire, _, start, end in _iter_field_spans(data):
        if number not in replacements:
            output.extend(data[start:end])
            continue
        if wire != replacements[number][0]:
            raise ModPackageError(f"unexpected wire type for household field {number}")
        if number in remainder:
            output.extend(_encode_field(number, *remainder.pop(number)))
    for number, (wire, value) in remainder.items():
        output.extend(_encode_field(number, wire, value))
    output.extend(data[end:])
    return bytes(output)


def _encode_field(number, wire, value):
    key = _encode_varint(number << 3 | wire)
    if wire == 2:
        return key + _encode_varint(len(value)) + value
    if wire == 5:
        return key + struct.pack("<f", value)
    return key + _encode_varint(value)


def _message(data: bytes, number: int, *, required: bool = False) -> bytes:
    messages = [value for tag, wire, value in iter_fields(data) if tag == number and wire == 2]
    if len(messages) > 1 or (required and not messages):
        raise ModPackageError(f"expected one embedded message at field {number}")
    return messages[0] if messages else b""


@dataclass(frozen=True)
class StarterMemberEdit:
    """Changes to one member of a starter household record.

    Every field defaults to ``None``, which leaves that part of the member
    unchanged.

    * ``trait_ids`` replaces the complete trait list, including age, species,
      preference, and other non-personality IDs.
    * ``skills`` maps skill IDs to raw skill XP, the unit the record stores.
      Listed skills are set and ``None`` removes a skill; unlisted skills stay.
      Convert a level with :meth:`sims4_sdk.skills.SkillCurve.xp_for_level`.
    * ``careers`` replaces the member's current careers; an empty sequence
      removes them. ``display_level`` defaults to ``track_level + 1``. The
      career history is kept.
    * ``aspiration_track_id`` sets the primary aspiration track.
    """

    trait_ids: Optional[Sequence[int]] = None
    skills: Optional[Mapping[int, Optional[float]]] = None
    careers: Optional[Sequence[StarterCareer]] = None
    aspiration_track_id: Optional[int] = None


def _uint64(value, label: str) -> int:
    if type(value) is not int or not 0 < value < 2**64:
        raise ModPackageError(f"{label} must be a positive uint64")
    return value


def _skill_entry(skill_id: int, xp: float) -> bytes:
    return _encode_field(1, 0, skill_id) + _encode_field(2, 5, xp)


def _edit_skills(container: bytes, skills: Mapping[int, Optional[float]]) -> bytes:
    """Edit ``PersistableSkillTracker.skills`` in place, keeping its order."""
    for skill_id, xp in skills.items():
        _uint64(skill_id, "skill IDs")
        if xp is not None and (isinstance(xp, bool) or not isinstance(xp, (int, float))
                               or not isfinite(xp) or xp < 0):
            raise ModPackageError("skill XP must be a finite, non-negative number or None")
    remaining = dict(skills)
    output = bytearray()
    end = 0
    for number, wire, entry, start, end in _iter_field_spans(container):
        skill_id = next((value for tag, kind, value in iter_fields(entry) if (tag, kind) == (1, 0)),
                        None) if (number, wire) == (1, 2) else None
        if skill_id not in skills:
            output.extend(container[start:end])
            continue
        if skill_id not in remaining:
            continue  # Drop a duplicate entry for an edited skill.
        xp = remaining.pop(skill_id)
        if xp is not None:
            output.extend(_encode_field(1, 2, _replace_fields(entry, {2: (5, float(xp))})))
    output.extend(container[end:])
    for skill_id, xp in remaining.items():
        if xp is not None:
            output.extend(_encode_field(1, 2, _skill_entry(skill_id, float(xp))))
    return bytes(output)


def _career_entry(career: StarterCareer, previous: bytes) -> bytes:
    if not isinstance(career, StarterCareer):
        raise ModPackageError("careers must be StarterCareer values")
    _uint64(career.career_id, "career IDs")
    _uint64(career.track_id, "career track IDs")
    level = career.track_level if career.track_level is not None else 0
    if type(level) is not int or not 0 <= level < 2**32:
        raise ModPackageError("career track_level must be a 0-based uint32")
    display = career.display_level if career.display_level is not None else level + 1
    if type(display) is not int or not 0 < display < 2**32:
        raise ModPackageError("career display_level must be a positive uint32")
    return _replace_fields(previous, {1: (0, career.career_id), 2: (0, career.track_id),
                                      3: (0, level), 4: (0, display)})


def _edit_careers(container: bytes, careers: Sequence[StarterCareer]) -> bytes:
    """Replace ``PersistableSimCareers.careers``; history and other fields stay."""
    existing = {}
    output = bytearray()
    end = 0
    for number, wire, entry, start, end in _iter_field_spans(container):
        if (number, wire) == (1, 2):
            career_id = next((value for tag, kind, value in iter_fields(entry) if (tag, kind) == (1, 0)), None)
            existing.setdefault(career_id, entry)
        else:
            output.extend(container[start:end])
    output.extend(container[end:])
    if len({career.career_id for career in careers}) != len(careers):
        raise ModPackageError("a member can hold each career only once")
    # An existing entry for the same career keeps its other fields, such as
    # the company name and join time.
    entries = b"".join(_encode_field(1, 2, _career_entry(career, existing.get(career.career_id, b"")))
                       for career in careers)
    return entries + bytes(output)


def _edit_member(member: bytes, edit: StarterMemberEdit) -> bytes:
    gameplay_fields: dict[int, tuple[int, int | bytes]] = {}
    gameplay = _message(member, 30)
    if edit.trait_ids is not None:
        ids = tuple(_uint64(value, "trait IDs") for value in edit.trait_ids)
        packed = b"".join(_encode_varint(value) for value in dict.fromkeys(ids))
        gameplay_fields[10] = (2, _replace_fields(_message(gameplay, 10), {1: (2, packed)}))
    if edit.careers is not None:
        gameplay_fields[12] = (2, _edit_careers(_message(gameplay, 12), tuple(edit.careers)))
    if edit.skills is not None:
        gameplay_fields[13] = (2, _edit_skills(_message(gameplay, 13), edit.skills))
    member_fields: dict[int, tuple[int, int | bytes]] = {}
    if gameplay_fields:
        member_fields[30] = (2, _replace_fields(gameplay, gameplay_fields))
    if edit.aspiration_track_id is not None:
        member_fields[34] = (0, _uint64(edit.aspiration_track_id, "aspiration track IDs"))
    return _replace_fields(member, member_fields)


def _edit_members(household: bytes, members: Mapping[int, StarterMemberEdit]) -> bytes:
    for sim_id, edit in members.items():
        _uint64(sim_id, "Sim IDs")
        if not isinstance(edit, StarterMemberEdit):
            raise ModPackageError("member edits must be StarterMemberEdit values")
    remaining = dict(members)
    output = bytearray()
    end = 0
    for number, wire, member, start, end in _iter_field_spans(household):
        sim_id = next((int.from_bytes(value, "little") for tag, kind, value in iter_fields(member)
                       if (tag, kind) == (1, 1)), None) if (number, wire) == (6, 2) else None
        if sim_id not in members:
            output.extend(household[start:end])
            continue
        if sim_id not in remaining:
            raise ModPackageError(f"duplicate household member with Sim ID {sim_id}")
        output.extend(_encode_field(6, 2, _edit_member(member, remaining.pop(sim_id))))
    if remaining:
        raise ModPackageError(f"Sim IDs do not belong to this household: {list(remaining)}")
    output.extend(household[end:])
    return bytes(output)


def starter_household_override(
    key: ResourceKey,
    source: bytes,
    *,
    name: str | None = None,
    description: str | None = None,
    funds: int | None = None,
    members: Mapping[int, StarterMemberEdit] | None = None,
) -> tuple[ResourceKey, bytes]:
    """Patch a version 0 or 2 starter household record.

    ``name`` and ``description`` set the record's inline text. Placed
    households show the text from their lot manifest instead, so use
    :func:`starter_household_text` to change what players see. ``members``
    maps the baked member IDs from ``parse_premade_household`` to edits.
    """
    if key.type_id != PREMADE_HOUSEHOLD_TYPE_ID:
        raise ModPackageError("expected a starter household resource key")
    if not isinstance(source, bytes):
        raise ModPackageError("expected the original starter household bytes")
    if name is None and description is None and funds is None and not members:
        raise ModPackageError("supply a household name, description, funds, or member edits")
    fields: dict[int, tuple[int, int | bytes]] = {}
    if name is not None:
        fields[3] = (2, _text(name, "household name", allow_empty=False))
    if description is not None:
        fields[11] = (2, _text(description, "household description", allow_empty=True))
    if funds is not None:
        if type(funds) is not int or not 0 <= funds <= 0xFFFFFFFF:
            raise ModPackageError("household funds must be a uint32")
        fields[4] = (0, funds)

    version = int.from_bytes(source[:4], "little")
    header_size = {0: 8, 2: 16}.get(version)
    if header_size is None or len(source) < header_size:
        raise ModPackageError("unsupported starter household header")
    length = struct.unpack_from("<I", source, header_size - 4)[0]
    end = header_size + length
    if end > len(source):
        raise ModPackageError("truncated starter household payload")
    payload = source[header_size:end]
    household = _replace_fields(_message(payload, 1, required=True), fields)
    if members:
        household = _edit_members(household, members)
    updated = _replace_fields(payload, {1: (2, household)})
    return key, source[:header_size - 4] + struct.pack("<I", len(updated)) + updated + source[end:]


def _text(value, label: str, *, allow_empty: bool) -> bytes:
    if not isinstance(value, str) or (not allow_empty and not value.strip()) or "\x00" in value:
        raise ModPackageError(f"{label} must be {'' if allow_empty else 'non-empty '}text without NULs")
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ModPackageError(f"{label} must be valid Unicode") from exc


def _standalone(element, references, active=frozenset()):
    if element.tag == "r":
        ref = element.get("x")
        target = references.resolve(element)
        if target is None or ref in active:
            raise ModPackageError(f"invalid combined tuning reference: {ref!r}")
        clone = _standalone(target, references, active | {ref})
        clone.attrib.pop("x", None)
        clone.attrib.update((key, value) for key, value in element.attrib.items() if key != "x")
    else:
        clone = ET.Element(element.tag, element.attrib)
        clone.text = element.text
        clone.extend(_standalone(child, references, active) for child in element)
    clone.tail = element.tail
    return clone


def _xml(element: ET.Element) -> bytes:
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def premade_template_override(
    source: TuningElement,
    fields: Mapping[str, ET.Element | None],
    *,
    group: int = 0,
) -> tuple[ResourceKey, bytes]:
    """Replace named top-level Sim or household template tunables.

    Supply complete tuning nodes such as `<V>`, `<U>` or `<L>`.
    The mapping key supplies the node's name, and None removes a node.
    """
    if (source.cls not in ("PremadeSimTemplate", "PremadeHouseholdTemplate")
            or source.tuning_type != "sim_template" or source.instance_id <= 0):
        raise ModPackageError("expected an existing premade Sim or household template")
    if not fields:
        raise ModPackageError("supply at least one template field")
    standalone = _standalone(source.element, source.references)
    for name, replacement in fields.items():
        if not name:
            raise ModPackageError("template field names must be non-empty")
        for child in list(standalone):
            if child.get("n") == name:
                standalone.remove(child)
        if replacement is not None:
            node = _standalone(replacement, source.references)
            node.set("n", name)
            standalone.append(node)
    return ResourceKey(SIM_TEMPLATE_TYPE_ID, group, source.instance_id), _xml(standalone)


def premade_relationship_override(
    source: CombinedTuning,
    pairs: Mapping[tuple[int, int], int | None],
    *,
    group: int = 0,
) -> tuple[ResourceKey, bytes]:
    """Set existing loot IDs for ordered pairs of premade Sim template IDs.

    A None value removes that ordered pair. Other entries and family fixups
    are retained from the supplied module.
    """
    module = source.find_module(RELATIONSHIPS_MODULE)
    if module is None or not pairs:
        raise ModPackageError("supply the premade relationship module and at least one pair")
    standalone = _standalone(module, source.references)
    relationship_map = standalone.find("./C[@n='PremadeSimRelationships']/L[@n='RELATIONSHIP_MAP']")
    if relationship_map is None:
        raise ModPackageError("premade relationship module has no RELATIONSHIP_MAP")
    instance = _module_instance(standalone, "premade relationship")
    for (a, b), loot in pairs.items():
        ids = (a, b) if loot is None else (a, b, loot)
        if a == b or any(type(value) is not int or not 0 < value < 2**64 for value in ids):
            raise ModPackageError("relationships require distinct Sim template IDs and a valid loot ID")
    remaining = dict(pairs)
    for row in list(relationship_map):
        try:
            pair = (int(row.findtext("./T[@n='sim_a']", ""), 0),
                    int(row.findtext("./T[@n='sim_b']", ""), 0))
        except ValueError:
            continue
        if pair in remaining:
            loot = remaining.pop(pair)
            if loot is None:
                relationship_map.remove(row)
            else:
                action = row.find("./T[@n='relationship_loot']")
                if action is None:
                    action = ET.SubElement(row, "T", n="relationship_loot")
                action.text = str(loot)
        elif pair in pairs:
            relationship_map.remove(row)
    for (a, b), loot in remaining.items():
        if loot is not None:
            row = ET.SubElement(relationship_map, "U")
            for name, value in (("sim_a", a), ("sim_b", b), ("relationship_loot", loot)):
                ET.SubElement(row, "T", n=name).text = str(value)
    return ResourceKey(TUNING_TYPE_ID, group, instance), _xml(standalone)


def relationship_loot(
    name: str,
    *,
    friendship: float | None = None,
    romance: float | None = None,
    bit_ids: Iterable[int] = (),
    group: int = 0,
) -> tuple[ResourceKey, bytes]:
    """Build a new relationship loot that sets exact track values and adds bits.

    The loot uses the shape of the game's premade loots: it sets each track
    from the Actor (``sim_a``) to the TargetSim (``sim_b``) and adds each bit
    the same way. Reference the returned instance ID from
    :func:`premade_relationship_override`. The instance ID is the FNV-64 hash
    of ``name``, so pick a name unique to your package.
    """
    if not isinstance(name, str) or not name.strip() or "\x00" in name:
        raise ModPackageError("loot name must be non-empty text without NULs")
    tracks = [(track, value) for track, value in ((FRIENDSHIP_TRACK_ID, friendship),
                                                  (ROMANCE_TRACK_ID, romance)) if value is not None]
    for _, value in tracks:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not -100 <= value <= 100:
            raise ModPackageError("relationship track values must be numbers from -100 to 100")
    bits = list(dict.fromkeys(_uint64(bit, "relationship bit IDs") for bit in bit_ids))
    if not tracks and not bits:
        raise ModPackageError("supply friendship, romance, or relationship bits")
    instance = fnv1_64(name)
    root = ET.Element("I", {"c": "LootActions", "i": "action", "m": "interactions.utils.loot",
                            "n": name, "s": str(instance)})
    actions = ET.SubElement(root, "L", n="loot_actions")
    for track, value in tracks:
        statistic = ET.SubElement(ET.SubElement(actions, "V", t="statistics"),
                                  "V", n="statistics", t="relationship_set")
        setting = ET.SubElement(statistic, "U", n="relationship_set")
        ET.SubElement(ET.SubElement(setting, "L", n="target_participant_type"), "E").text = "TargetSim"
        ET.SubElement(setting, "T", n="track").text = str(track)
        ET.SubElement(setting, "T", n="value").text = f"{value:g}"
    if bits:
        loot = ET.SubElement(ET.SubElement(actions, "V", t="relationship_bits_loot"),
                             "U", n="relationship_bits_loot")
        operations = ET.SubElement(loot, "L", n="bit_operations")
        for bit in bits:
            operation = ET.SubElement(operations, "U")
            ET.SubElement(operation, "T", n="bit").text = str(bit)
            for field_name, value in (("operation", "ADD"), ("recipients", "Actor"),
                                      ("targets", "TargetSim")):
                ET.SubElement(operation, "E", n=field_name).text = value
    ET.SubElement(root, "T", n="run_test_first").text = "True"
    return ResourceKey(ACTION_TUNING_TYPE_ID, group, instance), _xml(root)


def _module_instance(module: ET.Element, label: str) -> int:
    try:
        instance = int(module.get("s", ""), 0)
    except ValueError:
        instance = 0
    if instance <= 0:
        raise ModPackageError(f"{label} module has no valid instance ID")
    return instance


def initial_lot_traits_override(
    source: CombinedTuning,
    lots: Mapping[int, Iterable[int] | None],
    *,
    group: int = 0,
) -> tuple[ResourceKey, bytes]:
    """Set the lot traits that lots start with in a new save.

    ``lots`` maps house description IDs (``WorldLot.house_description_id``)
    to complete lists of lot trait IDs from ``Catalog.lot_traits``. ``None``
    or an empty list leaves the lot without starting traits. Other lots keep
    their entries from the supplied module.
    """
    module = source.find_module(LOT_TRAITS_MODULE)
    if module is None or not lots:
        raise ModPackageError("supply the lot trait module and at least one lot")
    standalone = _standalone(module, source.references)
    mapping = standalone.find("./C[@n='ZoneModifierTuning']/L[@n='INITIAL_ZONE_MODIFIERS']")
    if mapping is None:
        raise ModPackageError("lot trait module has no INITIAL_ZONE_MODIFIERS")
    instance = _module_instance(standalone, "lot trait")
    wanted: dict[int, list[int]] = {}
    for house, traits in lots.items():
        _uint64(house, "house description IDs")
        wanted[house] = list(dict.fromkeys(_uint64(trait, "lot trait IDs") for trait in traits or ()))
    for row in list(mapping):
        try:
            house = int(row.findtext("./T[@n='key']", ""), 0)
        except ValueError:
            continue
        if house in wanted:
            mapping.remove(row)
    for house, traits in wanted.items():
        if traits:
            row = ET.SubElement(mapping, "U")
            ET.SubElement(row, "T", n="key").text = str(house)
            values = ET.SubElement(row, "L", n="value")
            for trait in traits:
                ET.SubElement(values, "T").text = str(trait)
    return ResourceKey(TUNING_TYPE_ID, group, instance), _xml(standalone)
