"""Build package resources from existing new-save templates."""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping

from .catalog.relationships import RELATIONSHIPS_MODULE
from .core.combined_tuning import CombinedTuning, TuningElement
from .core.dbpf import ResourceKey, write_package
from .core.resource_types import PREMADE_HOUSEHOLD_TYPE_ID, SIM_TEMPLATE_TYPE_ID, TUNING_TYPE_ID
from .exceptions import Sims4SDKError
from .save.protobuf import _encode_varint, _iter_field_spans, iter_fields

__all__ = [
    "ModPackageError",
    "write_package",
    "starter_household_override",
    "premade_template_override",
    "premade_relationship_override",
]


class ModPackageError(Sims4SDKError, ValueError):
    """A template source or override is invalid."""


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
    return key + _encode_varint(value)


def _message(data: bytes, number: int, *, required: bool = False) -> bytes:
    messages = [value for tag, wire, value in iter_fields(data) if tag == number and wire == 2]
    if len(messages) > 1 or (required and not messages):
        raise ModPackageError(f"expected one embedded message at field {number}")
    return messages[0] if messages else b""


def _edit_member_traits(household: bytes, sim_traits: Mapping[int, Iterable[int]]) -> bytes:
    remaining = dict(sim_traits)
    output = bytearray()
    end = 0
    for number, wire, member, start, end in _iter_field_spans(household):
        if (number, wire) != (6, 2):
            output.extend(household[start:end])
            continue
        sim_id = next((int.from_bytes(value, "little") for tag, wire, value in iter_fields(member)
                       if (tag, wire) == (1, 1)), None)
        if sim_id not in sim_traits:
            output.extend(household[start:end])
            continue
        if sim_id not in remaining:
            raise ModPackageError(f"duplicate household member with Sim ID {sim_id}")
        ids = tuple(remaining.pop(sim_id))
        if any(type(value) is not int or not 0 < value < 2**64 for value in ids):
            raise ModPackageError("trait IDs must be positive uint64 values")
        packed = b"".join(_encode_varint(value) for value in dict.fromkeys(ids))
        gameplay = _message(member, 30)
        tracker = _replace_fields(_message(gameplay, 10), {1: (2, packed)})
        gameplay = _replace_fields(gameplay, {10: (2, tracker)})
        output.extend(_encode_field(6, 2, _replace_fields(member, {30: (2, gameplay)})))
    if remaining:
        raise ModPackageError(f"Sim IDs do not belong to this household: {list(remaining)}")
    output.extend(household[end:])
    return bytes(output)


def starter_household_override(
    key: ResourceKey,
    source: bytes,
    *,
    name: str | None = None,
    funds: int | None = None,
    sim_traits: Mapping[int, Iterable[int]] | None = None,
) -> tuple[ResourceKey, bytes]:
    """Patch a version 0 or 2 starter household.

    ``name`` sets the embedded name. Placed households may get their display
    name from a lot manifest instead. ``sim_traits`` maps baked member IDs to
    complete trait lists, including preference and other non-personality IDs.
    """
    if key.type_id != PREMADE_HOUSEHOLD_TYPE_ID:
        raise ModPackageError("expected a starter household resource key")
    if not isinstance(source, bytes):
        raise ModPackageError("expected the original starter household bytes")
    if name is None and funds is None and not sim_traits:
        raise ModPackageError("supply a household name, funds, or member traits")
    fields: dict[int, tuple[int, int | bytes]] = {}
    if name is not None:
        if not isinstance(name, str) or not name.strip() or "\x00" in name:
            raise ModPackageError("household name must be non-empty text without NULs")
        try:
            fields[3] = (2, name.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ModPackageError("household name must be valid Unicode") from exc
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
    if sim_traits:
        if any(type(value) is not int or not 0 < value < 2**64 for value in sim_traits):
            raise ModPackageError("Sim IDs must be positive uint64 values")
        household = _edit_member_traits(household, sim_traits)
    updated = _replace_fields(payload, {1: (2, household)})
    return key, source[:header_size - 4] + struct.pack("<I", len(updated)) + updated + source[end:]


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
    try:
        instance = int(standalone.get("s", ""), 0)
    except ValueError as exc:
        raise ModPackageError("premade relationship module has no valid instance ID") from exc
    if instance <= 0:
        raise ModPackageError("premade relationship module has no valid instance ID")
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
