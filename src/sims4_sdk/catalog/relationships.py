"""Initial relationship values from module-level tuning blocks.

The numeric friendship/romance values for pre-made Sims are not stored in
``0xB3C438F0`` and are not hardcoded.  They come from two module-level
``<M>`` tuning blocks:

``relationships.relationship_tracker_tuning``
    ``DefaultRelationshipInHousehold.RelationshipSetupMap`` maps a genealogy
    link (Roommate, FamilyMember, Spouse, Fiance, Steady, pets) to default track
    values.  ``HouseholdTemplate`` applies these through
    ``household.set_default_relationships()``.

``world.premade_sim_relationships``
    ``PremadeSimRelationships.RELATIONSHIP_MAP`` maps a pair of pre-made Sims
    in *different* households to a ``LootActions`` resource.  The loot sets the
    track values (``loot_Relationship_Starting_NPC_*``).

This module parses both blocks from a :class:`CombinedTuning` and resolves the
loot action chains into friendship/romance values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ..core import TuningElement
from ..core.combined_tuning import CombinedTuning
from .models import (
    PremadeRelationship,
    RelationshipDefault,
    RelationshipTrackValue,
)
from .values import TuningView

__all__ = [
    "DEFAULTS_MODULE",
    "GLOBAL_MODULE",
    "RELATIONSHIPS_MODULE",
    "RELATIONSHIP_MODULES",
    "FRIENDSHIP_TRACK_ID",
    "ROMANCE_TRACK_ID",
    "RelationshipTuningData",
    "extract_relationship_tuning",
    "has_interval_data",
]

DEFAULTS_MODULE = "relationships.relationship_tracker_tuning"
RELATIONSHIPS_MODULE = "world.premade_sim_relationships"
GLOBAL_MODULE = "relationships.global_relationship_tuning"
RELATIONSHIP_MODULES = (DEFAULTS_MODULE, RELATIONSHIPS_MODULE, GLOBAL_MODULE)

FRIENDSHIP_TRACK_ID = 16650
ROMANCE_TRACK_ID = 16651

_MAX_DEPTH = 32


@dataclass
class RelationshipTuningData:
    """Relationship defaults, cross-household pairs, and bit ranges."""

    defaults: dict[str, RelationshipDefault] = field(default_factory=dict)
    pairs: list[PremadeRelationship] = field(default_factory=list)
    track_ranges: dict[int, RelationshipTrackValue] = field(
        default_factory=dict, repr=False
    )
    steady_bit_id: Optional[int] = None
    engagement_bit_id: Optional[int] = None
    marriage_bit_id: Optional[int] = None
    family_trope_ids: list[int] = field(default_factory=list)
    romance_trope_ids: list[int] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"RelationshipTuningData(defaults={len(self.defaults)}, "
            f"pairs={len(self.pairs)}, ranges={len(self.track_ranges)}, "
            f"tropes={len(self.family_trope_ids) + len(self.romance_trope_ids)})"
        )


# ----------------------------------------------------------------------
# generic XML helpers (module blocks share the CT <g> reference table)
# ----------------------------------------------------------------------
def _resolve(ct: CombinedTuning, element):
    current = element
    depth = 0
    while current is not None and current.tag == "r" and depth < _MAX_DEPTH:
        current = ct.references.resolve(current)
        depth += 1
    return current


def _text(ct: CombinedTuning, element) -> Optional[str]:
    if element is None:
        return None
    resolved = _resolve(ct, element)
    if resolved is None:
        return None
    if resolved.text and resolved.text.strip():
        return resolved.text.strip()
    for child in resolved.iter():
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _integer(ct: CombinedTuning, element) -> Optional[int]:
    text = _text(ct, element)
    if text is None:
        return None
    try:
        return int(text, 0)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def _class_node(module, name: str):
    return next((node for node in module.iter("C") if node.get("n") == name), None)


def _list_node(element, name: str):
    return next((node for node in element if node.get("n") == name), None)


# ----------------------------------------------------------------------
# DefaultRelationshipInHousehold
# ----------------------------------------------------------------------
def _parse_defaults(ct: CombinedTuning) -> dict[str, RelationshipDefault]:
    module = ct.find_module(DEFAULTS_MODULE)
    if module is None:
        return {}
    class_node = _class_node(module, "DefaultRelationshipInHousehold")
    if class_node is None:
        return {}
    setup_map = _list_node(class_node, "RelationshipSetupMap")
    if setup_map is None:
        return {}

    defaults: dict[str, RelationshipDefault] = {}
    for entry in setup_map:
        fields = {child.get("n"): child for child in entry}
        link = _text(ct, fields.get("Family Link"))
        if not link:
            continue
        default = defaults.setdefault(link, RelationshipDefault(link=link))
        setup = fields.get("Default Relationship Setup")
        if setup is None:
            continue
        _merge_setup(ct, setup, default)
    return defaults


def _merge_setup(ct: CombinedTuning, setup, default: RelationshipDefault) -> None:
    for group in setup:
        for item in group:
            for field_element in item:
                name = field_element.get("n")
                if name == "relationship_tracks":
                    _merge_tracks(ct, field_element, default)
                elif name == "relationship_bits":
                    _merge_ids(ct, field_element, default.bit_ids)
                elif name == "_loots":
                    _merge_ids(ct, field_element, default.loot_ids)


def _merge_tracks(ct: CombinedTuning, element, default: RelationshipDefault) -> None:
    tracks = _resolve(ct, element)
    if tracks is None:
        return
    for track_entry in tracks:
        track_entry = _resolve(ct, track_entry)
        if track_entry is None:
            continue
        fields = {child.get("n"): child for child in track_entry}
        track_id = _integer(ct, fields.get("track"))
        value = _integer(ct, fields.get("value"))
        if track_id is None or value is None:
            continue
        existing = default.track(track_id)
        if existing is None:
            default.tracks.append(
                RelationshipTrackValue(
                    track_id=track_id,
                    value=float(value) if value is not None else None,
                )
            )
        elif value is not None:
            existing.value = float(value)


def _merge_ids(ct: CombinedTuning, element, target: list[int]) -> None:
    values = _resolve(ct, element)
    if values is None:
        return
    for item in values:
        number = _integer(ct, item)
        if number is not None and number not in target:
            target.append(number)


# ----------------------------------------------------------------------
# PremadeSimRelationships
# ----------------------------------------------------------------------
def _parse_pairs(
    ct: CombinedTuning,
    entries: Mapping[int, TuningElement],
    strings: Mapping[int, str],
) -> list[PremadeRelationship]:
    module = ct.find_module(RELATIONSHIPS_MODULE)
    if module is None:
        return []
    class_node = _class_node(module, "PremadeSimRelationships")
    if class_node is None:
        return []
    relmap = _list_node(class_node, "RELATIONSHIP_MAP")
    if relmap is None:
        return []

    pairs: list[PremadeRelationship] = []
    for entry in relmap:
        fields = {child.get("n"): child for child in entry}
        sim_a = _integer(ct, fields.get("sim_a"))
        sim_b = _integer(ct, fields.get("sim_b"))
        loot_id = _integer(ct, fields.get("relationship_loot"))
        if sim_a is None or sim_b is None:
            continue
        tracks, bits, sentiments = _evaluate_loot(loot_id, entries, strings)
        pairs.append(
            PremadeRelationship(
                sim_a=sim_a,
                sim_b=sim_b,
                tracks=tracks,
                bit_ids=bits,
                sentiment_track_ids=sentiments,
                loot_id=loot_id,
            )
        )
    return pairs


def _evaluate_loot(
    loot_id: Optional[int],
    entries: Mapping[int, TuningElement],
    strings: Mapping[int, str],
    seen: Optional[set[int]] = None,
) -> tuple[list[RelationshipTrackValue], list[int], list[int]]:
    """Follow nested ``actions`` loots and collect relationship track changes."""
    if loot_id is None:
        return [], [], []
    seen = seen or set()
    if loot_id in seen:
        return [], [], []
    seen.add(loot_id)

    element = entries.get(loot_id)
    if element is None or element.cls != "LootActions":
        return [], [], []

    view = TuningView(element, strings)
    actions = view.resolved_child("loot_actions")
    tracks: dict[int, RelationshipTrackValue] = {}
    bits: list[int] = []
    sentiments: list[int] = []
    if actions is None:
        return [], [], []

    for action in actions:
        resolved = view.resolve(action)
        if resolved is None:
            continue
        if resolved.tag == "T":
            nested = _text_of_element(view, resolved)
            if nested and nested.lstrip("-").isdigit():
                _merge_loot(nested, entries, strings, seen, tracks, bits, sentiments)
            continue
        if resolved.tag != "V":
            continue
        variant = resolved.get("t")
        inner = list(resolved)
        if variant == "actions" and inner:
            nested = _text_of_element(view, inner[0])
            if nested and nested.lstrip("-").isdigit():
                _merge_loot(nested, entries, strings, seen, tracks, bits, sentiments)
        elif variant == "statistics" and inner:
            _merge_statistics(view, inner[0], tracks, sentiments, entries)
        elif variant in ("relationship_bits", "relationship_bits_loot"):
            for child in inner:
                for candidate in child.iter():
                    text = _text_of_element(view, candidate)
                    if text and text.lstrip("-").isdigit():
                        bit_id = int(text)
                        if bit_id not in bits:
                            bits.append(bit_id)

    return list(tracks.values()), bits, sentiments


def _merge_loot(
    nested: str,
    entries: Mapping[int, TuningElement],
    strings: Mapping[int, str],
    seen: set[int],
    tracks: dict[int, RelationshipTrackValue],
    bits: list[int],
    sentiments: list[int],
) -> None:
    nested_tracks, nested_bits, nested_sentiments = _evaluate_loot(
        int(nested), entries, strings, seen
    )
    for item in nested_tracks:
        tracks[item.track_id] = item
    for bit in nested_bits:
        if bit not in bits:
            bits.append(bit)
    for track_id in nested_sentiments:
        if track_id not in sentiments:
            sentiments.append(track_id)


def _merge_statistics(
    view: TuningView,
    stats_variant,
    tracks: dict[int, RelationshipTrackValue],
    sentiments: list[int],
    entries: Mapping[int, TuningElement],
) -> None:
    payload = list(stats_variant)
    if not payload:
        return
    fields = {child.get("n"): child for child in payload[0]}
    track_text = _text_of_element(view, fields.get("track"))
    if track_text is None:
        return
    try:
        track_id = int(track_text)
    except ValueError:
        return
    value_text = _text_of_element(view, fields.get("value"))
    if track_id in (FRIENDSHIP_TRACK_ID, ROMANCE_TRACK_ID):
        value: Optional[float] = None
        if value_text is not None:
            try:
                value = float(value_text)
            except ValueError:
                value = None
        if value is not None:
            tracks[track_id] = RelationshipTrackValue(
                track_id=track_id, value=value
            )
    elif track_id not in sentiments:
        sentiments.append(track_id)


def _text_of_element(view: TuningView, element) -> Optional[str]:
    if element is None:
        return None
    return view.raw_text_of(element)


# ----------------------------------------------------------------------
# RelationshipTrack bit ranges
# ----------------------------------------------------------------------
def _parse_track_ranges(
    entries: Mapping[int, TuningElement],
    strings: Mapping[int, str],
    track_sources: Optional[Mapping[int, TuningElement]] = None,
) -> dict[int, RelationshipTrackValue]:
    ranges: dict[int, RelationshipTrackValue] = {}
    sources = track_sources or entries
    for track_id in (FRIENDSHIP_TRACK_ID, ROMANCE_TRACK_ID):
        element = sources.get(track_id)
        if element is None:
            element = entries.get(track_id)
        if element is None:
            continue
        view = TuningView(element, strings)
        bit_data = view.resolved_child("bit_data_tuning")
        if bit_data is None:
            continue
        for node in bit_data.iter():
            if node.tag != "U":
                continue
            fields = {child.get("n"): child for child in node}
            if "bit" not in fields:
                continue
            bit_id = _to_int(_text_of_element(view, fields.get("bit")))
            minimum = _to_int(_text_of_element(view, fields.get("minimum_value")))
            maximum = _to_int(_text_of_element(view, fields.get("maximum_value")))
            if minimum is None and maximum is None:
                add_value = _to_int(_text_of_element(view, fields.get("add_value")))
                remove_value = _to_int(_text_of_element(view, fields.get("remove_value")))
                if add_value is not None and remove_value is not None:
                    minimum = min(add_value, remove_value)
                    maximum = max(add_value, remove_value)
                elif add_value is not None:
                    minimum = maximum = add_value
            if bit_id is None:
                continue
            ranges[bit_id] = RelationshipTrackValue(
                track_id=track_id,
                min_value=float(minimum) if minimum is not None else None,
                max_value=float(maximum) if maximum is not None else None,
            )
    return ranges


def _to_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    try:
        return int(text, 0)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def has_interval_data(element: TuningElement) -> bool:
    """Return ``True`` if a relationship track carries bit interval values."""
    return any(
        child.get("n") in ("minimum_value", "maximum_value")
        for child in element.raw.iter()
    )


# ----------------------------------------------------------------------
# global relationship tuning (steady / fiance / marriage / tropes)
# ----------------------------------------------------------------------
def _parse_global(ct: CombinedTuning, data: RelationshipTuningData) -> None:
    module = ct.find_module(GLOBAL_MODULE)
    if module is None:
        return

    relationship = _class_node(module, "RelationshipGlobalTuning")
    if relationship is not None:
        fields = {child.get("n"): child for child in relationship}
        data.steady_bit_id = _integer(ct, fields.get("STEADY_RELATIONSHIP_BIT"))
        data.engagement_bit_id = _integer(
            ct, fields.get("ENGAGEMENT_RELATIONSHIP_BIT")
        )
        data.marriage_bit_id = _integer(ct, fields.get("MARRIAGE_RELATIONSHIP_BIT"))

    tropes = _class_node(module, "TropeGlobalTuning")
    if tropes is not None:
        fields = {child.get("n"): child for child in tropes}
        data.family_trope_ids = _list_ids(ct, fields.get("TROPES"))
        data.romance_trope_ids = _list_ids(ct, fields.get("ROMANCE_TROPES"))


def _list_ids(ct: CombinedTuning, element) -> list[int]:
    values = _resolve(ct, element)
    if values is None:
        return []
    ids: list[int] = []
    for item in values:
        number = _integer(ct, item)
        if number is not None and number not in ids:
            ids.append(number)
    return ids


# ----------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------
def extract_relationship_tuning(
    modules: Mapping[str, CombinedTuning],
    entries: Mapping[int, TuningElement],
    strings: Optional[Mapping[int, str]] = None,
    track_sources: Optional[Mapping[int, TuningElement]] = None,
) -> RelationshipTuningData:
    """Extract both relationship modules from the latest CTs that contain them."""
    strings = strings or {}
    data = RelationshipTuningData()

    defaults_ct = modules.get(DEFAULTS_MODULE)
    if defaults_ct is not None:
        data.defaults = _parse_defaults(defaults_ct)

    pairs_ct = modules.get(RELATIONSHIPS_MODULE)
    if pairs_ct is not None:
        data.pairs = _parse_pairs(pairs_ct, entries, strings)

    global_ct = modules.get(GLOBAL_MODULE)
    if global_ct is not None:
        _parse_global(global_ct, data)

    data.track_ranges = _parse_track_ranges(entries, strings, track_sources)

    for default in data.defaults.values():
        for item in default.tracks:
            element = entries.get(item.track_id)
            if element is not None:
                item.track_name = element.name
    for relationship in data.pairs:
        for item in relationship.tracks:
            element = entries.get(item.track_id)
            if element is not None:
                item.track_name = element.name
    return data
