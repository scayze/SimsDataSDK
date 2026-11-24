"""Lot traits and lot challenges, and the lot traits a new save starts with.

A lot trait is ``ZoneModifier`` tuning. Its name, description, icon, and kind
live in a separate ``ZoneModifierDisplayInfo`` instance that references the
zone modifier, so only zone modifiers with display info are user-facing.

The ``zone_modifier.zone_modifier_tuning`` module maps house description IDs
(the instance IDs of the ``0x729F6C4F`` lot manifests) to the zone modifiers a
lot gets when a new save is created (``INITIAL_ZONE_MODIFIERS``).
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..core.combined_tuning import CombinedTuning, TuningElement
from ..core.dbpf import ResourceKey
from ..core.fnv import fnv1_64
from ..core.resource_types import SIMDATA_TYPE_ID
from .models import LotTrait, TuningSource
from .values import TuningView

__all__ = ["LOT_TRAITS_MODULE", "LOT_TRAITS_SIMDATA_KEY", "extract_lot_traits",
           "extract_initial_lot_traits"]

LOT_TRAITS_MODULE = "zone_modifier.zone_modifier_tuning"
LOT_TRAITS_SIMDATA_TABLE = f"{LOT_TRAITS_MODULE}.ZoneModifierTuning"
#: The compiled client copy of the module that new saves take starting traits
#: from. Its instance is the FNV-64 hash of the lowercased module and class.
LOT_TRAITS_SIMDATA_KEY = ResourceKey(SIMDATA_TYPE_ID, 0x006CA304,
                                     fnv1_64(LOT_TRAITS_SIMDATA_TABLE.lower()))
_INITIAL_PATH = "./C[@n='ZoneModifierTuning']/L[@n='INITIAL_ZONE_MODIFIERS']"


def extract_lot_traits(
    entries: Mapping[int, TuningElement],
    sources: Mapping[int, TuningSource],
    strings: Mapping[int, str],
) -> dict[int, LotTrait]:
    """Build lot traits from display info that references a zone modifier."""
    traits: dict[int, LotTrait] = {}
    for instance_id, entry in entries.items():
        if entry.cls != "ZoneModifierDisplayInfo":
            continue
        view = TuningView(entry, strings)
        modifier_id = view.number("zone_modifier_reference")
        modifier = entries.get(modifier_id) if modifier_id else None
        if modifier is None or modifier.cls != "ZoneModifier":
            continue
        traits[modifier_id] = LotTrait(
            id=modifier_id,
            name=modifier.name,
            display_name=view.text("zone_modifier_name"),
            description=view.text("zone_modifier_description"),
            # The tunable defaults to LOT_TRAIT when the field is omitted.
            kind=view.enum("modifier_type") or "LOT_TRAIT",
            icon=view.text("zone_modifier_icon"),
            display_info_id=instance_id,
            source=sources.get(modifier_id),
        )
    return traits


def extract_initial_lot_traits(module: Optional[CombinedTuning]) -> dict[int, list[int]]:
    """Read ``INITIAL_ZONE_MODIFIERS`` as house description ID -> zone modifier IDs."""
    if module is None:
        return {}
    root = module.find_module(LOT_TRAITS_MODULE)
    mapping = root.find(_INITIAL_PATH) if root is not None else None
    if mapping is None:
        return {}
    references = module.references

    def resolve(element):
        depth = 0
        while element is not None and element.tag == "r" and depth < 16:
            element = references.resolve(element)
            depth += 1
        return element

    def number(element) -> Optional[int]:
        element = resolve(element)
        try:
            return int((element.text or "").strip(), 0) if element is not None else None
        except ValueError:
            return None

    result: dict[int, list[int]] = {}
    for row in mapping:
        row = resolve(row)
        if row is None:
            continue
        fields = {child.get("n"): child for child in row}
        key = number(fields.get("key"))
        value = resolve(fields.get("value"))
        if not key or value is None:
            continue
        items = [resolve(item) for item in value] if value.tag == "L" else [value]
        ids = [identifier for identifier in map(number, items) if identifier]
        result[key] = list(dict.fromkeys(ids))
    return result
